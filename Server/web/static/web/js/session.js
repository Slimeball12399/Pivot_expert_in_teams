// Session page (session.html): the talk slider moves the playhead of every
// timeline chart and updates the time above it ("0:35 / 1:00").
// Loaded after timeline-chart.js, so the charts exist when this runs.
document.addEventListener("DOMContentLoaded", function () {
    var slider = document.getElementById("talk-slider");
    if (!slider) {
        return;
    }
    var timeLabel = document.getElementById("talk-time");
    var max = Number(slider.max);
    document.getElementById("talk-time-total").textContent =
        "/ " + Math.floor(max / 60) + ":" + String(Math.floor(max % 60)).padStart(2, "0");

    function update() {
        var t = Number(slider.value);
        timeLabel.textContent = Math.floor(t / 60) + ":" + String(Math.floor(t % 60)).padStart(2, "0");
        // How far along the track is filled (used by the CSS for the ink part).
        slider.style.setProperty("--progress", (t - slider.min) / (max - slider.min) * 100 + "%");
        document.querySelectorAll("[data-timeline-chart]").forEach(function (chart) {
            if (chart.timeline) {
                chart.timeline.setTime(t);
            }
        });
    }

    slider.addEventListener("input", update);
    update();
});
