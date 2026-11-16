// Talk page (talk.html): DEMO DATA ONLY. Puts 40 made-up points on the polar
// chart (a random sway near the centre) so the page can be looked at before
// real data exists. Delete this file (and its <script> in talk.html) then.
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
    document.getElementById("balance-polar").polarChart.setData(points);
});
