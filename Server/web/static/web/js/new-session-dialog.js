// New session dialog (web/components/new_session_dialog.html).
//
// Opens with a button id="new-session-open"; closes with Escape, Cancel, the
// cross or a click on the backdrop. Closing resets it.
// User search: from 2 characters it asks the server (data-speakers-url,
// web:invite_suggestions with own=1) for the trainer's own users whose name or email
// contains what you typed, 200ms after the last keystroke, and cancels a
// request that is no longer needed. Arrow keys move through the list, Enter
// or a click picks one, Escape closes the list. A picked user replaces the
// search field until Change; the checkbox then names their phone.
// Now / Later: Later shows the date and time and the button says Save; Now
// hides them and the button says Start. The picker is in local time; the form
// sends scheduled_at as UTC (toISOString).
// Start / Save post the form to web:sessions: on success the page reloads
// (with the toast); errors show under their field and the dialog stays open.
document.addEventListener("DOMContentLoaded", function () {
    var dialog = document.getElementById("new-session-dialog");
    var opener = document.getElementById("new-session-open");
    if (!dialog || !opener) {
        return;
    }
    var form = dialog.querySelector("form");
    var search = document.getElementById("new-session-search");
    var input = document.getElementById("new-session-speaker");
    var list = document.getElementById("new-session-suggestions");
    var hint = document.getElementById("new-session-speaker-hint");
    var speakerField = document.getElementById("new-session-speaker-field");
    var speakerError = document.getElementById("new-session-speaker-error");
    var speakerId = document.getElementById("new-session-speaker-id");
    var picked = document.getElementById("new-session-picked");
    var change = document.getElementById("new-session-change");
    var phone = document.getElementById("new-session-phone");
    var phoneLabel = phone.closest("label").querySelector(".checkbox-label");
    var phoneLabelText = phoneLabel.textContent;
    var timeField = document.getElementById("new-session-time-field");
    var time = document.getElementById("new-session-time");
    var timeError = document.getElementById("new-session-time-error");
    var scheduledAt = document.getElementById("new-session-scheduled-at");
    var generalError = document.getElementById("new-session-error");
    var submit = document.getElementById("new-session-submit");
    var speakersUrl = dialog.dataset.speakersUrl;
    var MIN_LENGTH = 2;
    var DELAY_MS = 200;
    var matches = [];  // the speakers in the list, in order
    var active = -1;
    var timer = null;
    var pending = null;  // AbortController of the request in flight

    function options() {
        return list.querySelectorAll("[role=option]");
    }

    function cancelRequest() {
        clearTimeout(timer);
        if (pending) {
            pending.abort();
            pending = null;
        }
    }

    function closeList() {
        cancelRequest();
        list.hidden = true;
        list.replaceChildren();
        matches = [];
        input.setAttribute("aria-expanded", "false");
        input.removeAttribute("aria-activedescendant");
        active = -1;
    }

    function setActive(index) {
        var items = options();
        items.forEach(function (item, i) {
            item.setAttribute("aria-selected", String(i === index));
        });
        active = index;
        if (index >= 0) {
            input.setAttribute("aria-activedescendant", items[index].id);
            items[index].scrollIntoView({block: "nearest"});
        } else {
            input.removeAttribute("aria-activedescendant");
        }
    }

    function initials(speaker) {
        return ((speaker.first_name || "").charAt(0) + (speaker.last_name || "").charAt(0)).toUpperCase();
    }

    function pick(speaker) {
        closeList();
        clearErrors();
        speakerId.value = speaker.id;
        document.getElementById("new-session-picked-initials").textContent = initials(speaker);
        document.getElementById("new-session-picked-name").textContent =
            speaker.first_name + " " + speaker.last_name;
        document.getElementById("new-session-picked-email").textContent = speaker.email;
        phoneLabel.textContent = "Stream to " + speaker.first_name + "'s phone";
        search.hidden = true;
        hint.hidden = true;
        picked.hidden = false;
        change.focus();
    }

    function unpick() {
        speakerId.value = "";
        input.value = "";
        phoneLabel.textContent = phoneLabelText;
        picked.hidden = true;
        search.hidden = false;
        hint.hidden = false;
    }

    // Ask the server for the trainer's users, a moment after the last keystroke.
    function suggest() {
        var query = input.value.trim();
        cancelRequest();
        if (query.length < MIN_LENGTH) {
            closeList();
            return;
        }
        timer = setTimeout(function () {
            pending = new AbortController();
            fetch(speakersUrl + "?" + new URLSearchParams({q: query, own: "1"}), {
                headers: {"Accept": "application/json"},
                signal: pending.signal,
            })
                .then(function (response) {
                    if (!response.ok) {
                        throw new Error("Speaker search failed: " + response.status);
                    }
                    return response.json();
                })
                .then(function (data) {
                    pending = null;
                    render(data.suggestions);
                })
                .catch(function (error) {
                    if (error.name !== "AbortError") {
                        console.warn(error);
                    }
                });
        }, DELAY_MS);
    }

    function render(speakers) {
        list.replaceChildren();
        matches = speakers;
        active = -1;
        if (speakers.length === 0) {
            var empty = document.createElement("li");
            empty.className = "combobox-empty";
            empty.textContent = "None of your users match.";
            list.append(empty);
        }
        speakers.forEach(function (speaker, i) {
            var item = document.createElement("li");
            item.id = "new-session-suggestion-" + i;
            item.className = "combobox-option";
            item.setAttribute("role", "option");
            item.setAttribute("aria-selected", "false");

            var badge = document.createElement("span");
            badge.className = "session-speaker-initials";
            badge.setAttribute("aria-hidden", "true");
            badge.textContent = initials(speaker);
            var text = document.createElement("span");
            text.className = "session-speaker-text";
            var name = document.createElement("strong");
            name.textContent = speaker.first_name + " " + speaker.last_name;
            var email = document.createElement("span");
            email.className = "session-speaker-email";
            email.textContent = speaker.email;
            text.append(name, email);
            item.append(badge, text);
            // mousedown, not click, so the input keeps focus.
            item.addEventListener("mousedown", function (event) {
                event.preventDefault();
                pick(speaker);
            });
            list.append(item);
        });
        list.hidden = false;
        input.setAttribute("aria-expanded", "true");
    }

    // Now: no time, Start. Later: the time, Save.
    function updateStart() {
        var later = form.elements.start.value === "later";
        timeField.hidden = !later;
        submit.textContent = later ? "Save" : "Start";
        if (later) {
            // The earliest choice is now, in local time ("YYYY-MM-DDTHH:MM").
            var now = new Date();
            now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
            time.min = now.toISOString().slice(0, 16);
        }
    }

    function showError(element, message) {
        element.textContent = message;
        element.hidden = false;
    }

    function clearErrors() {
        [speakerError, timeError, generalError].forEach(function (element) {
            element.hidden = true;
            element.textContent = "";
        });
        speakerField.classList.remove("input-field-error");
        timeField.classList.remove("input-field-error");
    }

    form.addEventListener("submit", function (event) {
        event.preventDefault();
        closeList();
        clearErrors();
        // A datetime-local value has no time zone: the browser reads it as
        // local time, toISOString() turns it into UTC.
        scheduledAt.value = form.elements.start.value === "later" && time.value
            ? new Date(time.value).toISOString() : "";
        submit.disabled = true;
        fetch(form.action, {
            method: "POST",
            body: new FormData(form),  // includes the CSRF token
            headers: {"Accept": "application/json"},
        })
            .then(function (response) {
                return response.json().then(function (data) {
                    return {ok: response.ok, data: data};
                });
            })
            .then(function (result) {
                if (result.ok) {
                    window.location.reload();
                    return;
                }
                var errors = result.data.errors || {};
                Object.keys(errors).forEach(function (name) {
                    if (name === "speaker_id") {
                        speakerField.classList.add("input-field-error");
                        showError(speakerError, errors[name][0]);
                    } else if (name === "scheduled_at") {
                        timeField.classList.add("input-field-error");
                        showError(timeError, errors[name][0]);
                    } else {
                        showError(generalError, errors[name][0]);
                    }
                });
                if (!Object.keys(errors).length) {
                    showError(generalError, "Couldn't save the session.");
                }
                submit.disabled = false;
            })
            .catch(function () {
                showError(generalError, "Couldn't save the session. Check your connection and try again.");
                submit.disabled = false;
            });
    });

    form.querySelectorAll("input[name=start]").forEach(function (radio) {
        radio.addEventListener("change", function () {
            timeError.hidden = true;
            timeField.classList.remove("input-field-error");
            updateStart();
        });
    });

    change.addEventListener("click", function () {
        unpick();
        input.focus();
    });

    dialog.querySelectorAll("[data-dialog-close], #new-session-cancel").forEach(function (button) {
        button.addEventListener("click", function () {
            dialog.close();
        });
    });

    opener.addEventListener("click", function () {
        dialog.showModal();
        input.focus();
    });

    // A click on the dialog element itself is a click on the backdrop.
    dialog.addEventListener("click", function (event) {
        if (event.target === dialog) {
            dialog.close();
        }
    });

    dialog.addEventListener("close", function () {
        closeList();
        clearErrors();
        unpick();
        form.reset();
        updateStart();
        submit.disabled = false;
    });

    input.addEventListener("input", suggest);
    input.addEventListener("blur", closeList);

    input.addEventListener("keydown", function (event) {
        var count = options().length;
        if (event.key === "ArrowDown" && count) {
            event.preventDefault();
            setActive((active + 1) % count);
        } else if (event.key === "ArrowUp" && count) {
            event.preventDefault();
            setActive(active <= 0 ? count - 1 : active - 1);
        } else if (event.key === "Enter") {
            // Enter picks; it never submits from the search field.
            event.preventDefault();
            if (active >= 0) {
                pick(matches[active]);
            }
        } else if (event.key === "Escape" && !list.hidden) {
            // Close only the list; a second Escape closes the dialog.
            event.preventDefault();
            closeList();
        }
    });
});
