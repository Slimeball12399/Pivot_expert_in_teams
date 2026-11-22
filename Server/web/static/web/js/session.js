// Session content (content/session_content.html): draws everything that
// changes from the session's JSON, the same as GET web:session with
// Accept: application/json:
//   {"session": {"id", "status", "started_at", "ended_at"},
//    "talks": [{"id", "number", "status", "started_at", "duration" (seconds or
//               null), "speech", "stability" (0 to 100 or null), "url"}],
//    "talk", "voice_config", "stability_config", "speech_score", "stability_score"}
// the last five are the graphs of the talk shown (get_talk_graphs), the same
// as one talk's JSON (web:talk).
//
// On load it reads it from <script id="session-data"> if the page has it (the
// session page); without it (the live screen) it waits for refresh(). Then:
//   render(data)   the talk rows (copies of #talk-row-template), the header's
//                  talk count and the graphs of data's talk
//   showTalk(data) only the graphs: both charts, both score rings, the
//                  slider back at the start; that talk's row aria-current
//   refresh()      GET the session's JSON again and render it (the live
//                  screen, when a talk starts or ends); resolves with the JSON
// on the content element as content.session, for other scripts. The eye in a
// row fetches that talk (web:talk) and shows it. The slider moves the
// playhead of both charts and updates the time above it ("0:35 / 1:00").
// Loaded after timeline-chart.js and score-ring.js, so the charts exist.
document.addEventListener("DOMContentLoaded", function () {
    var content = document.querySelector("[data-session-content]");
    if (!content) {
        return;
    }
    var slider = document.getElementById("talk-slider");
    var timeLabel = document.getElementById("talk-time");
    var totalLabel = document.getElementById("talk-time-total");
    var rows = content.querySelector("[data-talk-rows]");
    var rowTemplate = document.getElementById("talk-row-template");
    var emptyTemplate = document.getElementById("talk-empty-template");
    var charts = content.querySelectorAll("[data-timeline-chart]");
    var shownId = null;  // the talk in the graphs

    // "m:ss", or "h:mm:ss" from an hour up.
    function clock(seconds) {
        seconds = Math.round(seconds);
        var hours = Math.floor(seconds / 3600);
        var minutes = Math.floor(seconds % 3600 / 60);
        return (hours ? hours + ":" + String(minutes).padStart(2, "0") : minutes)
            + ":" + String(seconds % 60).padStart(2, "0");
    }

    function updateTime() {
        var t = Number(slider.value);
        var max = Number(slider.max);
        timeLabel.textContent = clock(t);
        totalLabel.textContent = "/ " + clock(max);
        // How far along the track is filled (used by the CSS for the ink part).
        slider.style.setProperty("--progress", (max ? (t - slider.min) / (max - slider.min) : 0) * 100 + "%");
        charts.forEach(function (chart) {
            if (chart.timeline) {
                chart.timeline.setTime(t);
            }
        });
    }

    function showTalk(graphs) {
        document.getElementById("voice-chart").timeline.setConfig(graphs.voice_config);
        document.getElementById("stability-chart").timeline.setConfig(graphs.stability_config);
        document.getElementById("voice-score").scoreRing.setValue(graphs.speech_score || 0);
        document.getElementById("stability-score").scoreRing.setValue(graphs.stability_score || 0);
        slider.max = graphs.voice_config.x.max;
        slider.value = 0;
        updateTime();
        shownId = graphs.talk ? graphs.talk.id : null;
        rows.querySelectorAll("[data-talk-row]").forEach(function (row) {
            if (row.dataset.talkRow === shownId) {
                row.setAttribute("aria-current", "true");
            } else {
                row.removeAttribute("aria-current");
            }
        });
    }

    function render(data) {
        var count = data.talks.length;
        document.querySelectorAll("[data-session-talk-count]").forEach(function (element) {
            element.textContent = count + (count === 1 ? " talk" : " talks");
        });

        rows.replaceChildren();
        if (!count) {
            rows.append(emptyTemplate.content.cloneNode(true));
        }
        data.talks.forEach(function (talk) {
            var row = rowTemplate.content.cloneNode(true);
            var name = "Talk " + talk.number;
            row.querySelector("[data-talk-row]").dataset.talkRow = talk.id;
            row.querySelector("[data-field=name]").textContent = name;
            row.querySelector("[data-field=started]").textContent = new Date(talk.started_at)
                .toLocaleTimeString([], {hour: "2-digit", minute: "2-digit", hourCycle: "h23"});
            row.querySelector("[data-field=length]").textContent =
                talk.duration === null ? "–" : clock(talk.duration);
            // The two score bars: the rounded score and a line as long as it, or a dash.
            [["speech", "Speech", talk.speech], ["stability", "Stability", talk.stability]].forEach(function (score) {
                var bar = row.querySelector("[data-score=" + score[0] + "]");
                var value = bar.querySelector("[data-field=value]");
                var label = bar.querySelector("[data-field=label]");
                bar.style.setProperty("--value", score[2] === null ? 0 : score[2]);
                if (score[2] === null) {
                    value.textContent = "–";
                    value.classList.add("score-bar-none");
                    label.textContent = "No " + score[0] + " score yet";
                } else {
                    value.textContent = Math.round(score[2]);
                    label.textContent = score[1] + " score " + Math.round(score[2]) + " of 100";
                }
            });
            row.querySelector("[data-field=delete]").setAttribute("aria-label", "Delete " + name.toLowerCase());
            var show = row.querySelector("[data-field=show]");
            show.setAttribute("aria-label", "Show " + name.toLowerCase());
            show.dataset.talkUrl = talk.url;
            rows.append(row);
        });

        showTalk(data);
    }

    function refresh() {
        return fetch(content.dataset.sessionUrl, {headers: {"Accept": "application/json"}})
            .then(function (response) {
                if (!response.ok) {
                    throw new Error("Session failed: " + response.status);
                }
                return response.json();
            })
            .then(function (data) {
                render(data);
                return data;
            });
    }

    // The eye: that talk's graphs. One listener for all rows, as they are redrawn.
    rows.addEventListener("click", function (event) {
        var button = event.target.closest("[data-talk-url]");
        if (!button) {
            return;
        }
        button.disabled = true;
        fetch(button.dataset.talkUrl, {headers: {"Accept": "application/json"}})
            .then(function (response) {
                if (!response.ok) {
                    throw new Error("Talk graphs failed: " + response.status);
                }
                return response.json();
            })
            .then(showTalk)
            .catch(function (error) {
                // The graphs stay on the talk they showed.
                console.warn(error);
            })
            .finally(function () {
                button.disabled = false;
            });
    });

    slider.addEventListener("input", updateTime);

    content.session = {render: render, showTalk: showTalk, refresh: refresh};
    var embedded = document.getElementById("session-data");
    if (embedded) {
        render(JSON.parse(embedded.textContent));
    }
});
