// Talk content (talk_content.html, on the live screen): DEMO DATA ONLY. Puts 40
// made-up points on the polar chart (a random sway near the centre), so the
// stability card can be looked at before there is board data. The voice graph
// is live (live.js). Delete this file (and its <script> in talk_content.html)
// once the board's data comes.
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
});
