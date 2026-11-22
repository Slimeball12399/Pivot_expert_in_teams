// Talk content (talk_content.html, on the live screen): DEMO DATA ONLY. Puts 40 made-up points on the polar
// chart (a random sway near the centre) and made-up pace and pitch variation
// scores on the voice graph, so the page can be looked at before
// real data exists. Delete this file (and its <script> in talk_content.html) then.
document.addEventListener("DOMContentLoaded", function () {
    // A point with a speed that gets small random pushes, a pull back to the
    // centre and some damping, so the trail drifts like a person standing.
    var lr = 0, fb = 0, speedLr = 0, speedFb = 0;
    var points = [];
    for (var i = 0; i < 40; i++) {
        speedLr = speedLr * 0.9 - lr * 0.02 + (Math.random() - 0.5) * 0.6;
        speedFb = speedFb * 0.9 - fb * 0.02 + (Math.random() - 0.5) * 0.6;
        lr += speedLr;
        fb += speedFb;
        points.push([lr, fb]);
    }
    document.getElementById("live-balance-polar").polarChart.setData(points);

    // Voice graph: a pace and pitch variation score every 5 seconds, like the
    // live data, from 1:00 to 1:30 of the talk, kept within -10 to +10. The
    // chart shows the 1:00-2:00 minute, half written.
    var pace = [], pitch = [], paceScore = 1, pitchScore = 3;
    for (var second = 60; second <= 90; second += 5) {
        paceScore = Math.max(-10, Math.min(10, paceScore * 0.7 + (Math.random() - 0.5) * 6));
        pitchScore = Math.max(-10, Math.min(10, pitchScore * 0.7 + (Math.random() - 0.5) * 7));
        pace.push([second, paceScore]);
        pitch.push([second, pitchScore]);
    }
    document.getElementById("live-voice-chart").timeline.setData(pace, null, pitch);
});
