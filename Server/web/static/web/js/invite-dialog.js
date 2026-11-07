// Invite dialog on the Users page. Send invite just closes the dialog for now.
//
// Opens with the Invite user button; closes with Escape, Cancel, the cross or
// a click on the backdrop. The email field is a combobox: from 3 characters it
// asks the server (data-suggestions-url, web:invite_suggestions) for speaker
// emails that start with what you typed, 200ms after the last keystroke, and
// cancels a request that is no longer needed. Arrow keys move through the
// list, Enter or a click picks one, Escape closes the list.
document.addEventListener("DOMContentLoaded", function () {
    var dialog = document.getElementById("invite-dialog");
    var opener = document.getElementById("invite-open");
    if (!dialog || !opener) {
        return;
    }
    var input = document.getElementById("invite-email");
    var list = document.getElementById("invite-suggestions");
    var suggestionsUrl = dialog.dataset.suggestionsUrl;
    var MIN_LENGTH = 3;  // the server answers nothing shorter (SUGGEST_MIN_LENGTH)
    var DELAY_MS = 200;
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

    function pick(email) {
        input.value = email;
        closeList();
        input.focus();
    }

    // Ask the server for suggestions, a moment after the last keystroke.
    function suggest() {
        var query = input.value.trim();
        cancelRequest();
        if (query.length < MIN_LENGTH) {
            closeList();
            return;
        }
        timer = setTimeout(function () {
            pending = new AbortController();
            fetch(suggestionsUrl + "?" + new URLSearchParams({q: query}), {
                headers: {"Accept": "application/json"},
                signal: pending.signal,
            })
                .then(function (response) {
                    if (!response.ok) {
                        throw new Error("Suggestions failed: " + response.status);
                    }
                    return response.json();
                })
                .then(function (data) {
                    pending = null;
                    render(data.suggestions);
                })
                .catch(function (error) {
                    if (error.name !== "AbortError") {
                        // No suggestions is fine: the email can still be typed in full.
                        console.warn(error);
                    }
                });
        }, DELAY_MS);
    }

    function render(matches) {
        list.replaceChildren();
        active = -1;
        if (matches.length === 0) {
            var empty = document.createElement("li");
            empty.className = "combobox-empty";
            empty.textContent = "No speaker with that email yet. You can still invite them.";
            list.append(empty);
        }
        matches.forEach(function (match, i) {
            var item = document.createElement("li");
            item.id = "invite-suggestion-" + i;
            item.className = "combobox-option";
            item.setAttribute("role", "option");
            item.setAttribute("aria-selected", "false");

            var email = document.createElement("span");
            email.className = "combobox-option-email";
            email.textContent = match.email;
            item.append(email);
            if (match.already_linked) {
                var tag = document.createElement("span");
                tag.className = "combobox-tag";
                tag.textContent = "Already your speaker";
                item.append(tag);
            }
            // mousedown, not click, so the input keeps focus.
            item.addEventListener("mousedown", function (event) {
                event.preventDefault();
                pick(match.email);
            });
            list.append(item);
        });
        list.hidden = false;
        input.setAttribute("aria-expanded", "true");
    }

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
        input.value = "";
        closeList();
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
        } else if (event.key === "Enter" && active >= 0) {
            event.preventDefault();
            pick(options()[active].querySelector(".combobox-option-email").textContent);
        } else if (event.key === "Escape" && !list.hidden) {
            // Close only the list; a second Escape closes the dialog.
            event.preventDefault();
            closeList();
        }
    });
});
