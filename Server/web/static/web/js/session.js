// Session page (session.html): the talk slider moves the playhead of every
// timeline chart and updates the time above it ("0:35 / 1:00"). The eye in the
// talks card shows another talk: it fetches its graphs (web:talk, JSON from
// get_talk_graphs), redraws both charts and score rings, puts the slider back
// at the start of that talk and marks its row aria-current.
// Loaded after timeline-chart.js and score-ring.js, so the charts exist when this runs.
document.addEventListener("DOMContentLoaded", function () {
    var slider = document.getElementById("talk-slider");
    if (!slider) {
        return;
    }
    var timeLabel = document.getElementById("talk-time");
    var totalLabel = document.getElementById("talk-time-total");

    function clock(seconds) {
        return Math.floor(seconds / 60) + ":" + String(Math.floor(seconds % 60)).padStart(2, "0");
    }

    function update() {
        var t = Number(slider.value);
        var max = Number(slider.max);
        timeLabel.textContent = clock(t);
        totalLabel.textContent = "/ " + clock(max);
        // How far along the track is filled (used by the CSS for the ink part).
        slider.style.setProperty("--progress", (max ? (t - slider.min) / (max - slider.min) : 0) * 100 + "%");
        document.querySelectorAll("[data-timeline-chart]").forEach(function (chart) {
            if (chart.timeline) {
                chart.timeline.setTime(t);
            }
        });
    }

    slider.addEventListener("input", update);
    update();

    document.querySelectorAll("[data-talk-url]").forEach(function (button) {
        button.addEventListener("click", function () {
            button.disabled = true;
            fetch(button.dataset.talkUrl, {headers: {"Accept": "application/json"}})
                .then(function (response) {
                    if (!response.ok) {
                        throw new Error("Talk graphs failed: " + response.status);
                    }
                    return response.json();
                })
                .then(function (data) {
                    document.getElementById("voice-chart").timeline.setConfig(data.voice_config);
                    document.getElementById("stability-chart").timeline.setConfig(data.stability_config);
                    document.getElementById("voice-score").scoreRing.setValue(data.speech_score || 0);
                    document.getElementById("stability-score").scoreRing.setValue(data.stability_score || 0);
                    slider.max = data.voice_config.x.max;
                    slider.value = 0;
                    update();
                    document.querySelectorAll("[data-talk-row]").forEach(function (row) {
                        if (row.dataset.talkRow === data.talk.id) {
                            row.setAttribute("aria-current", "true");
                        } else {
                            row.removeAttribute("aria-current");
                        }
                    });
                })
                .catch(function (error) {
                    // The graphs stay on the talk they showed.
                    console.warn(error);
                })
                .finally(function () {
                    button.disabled = false;
                });
        });
    });
});
