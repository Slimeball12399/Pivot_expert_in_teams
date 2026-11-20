// Score ring (web/components/score_ring.html): a progress ring with the score
// in the middle and a label under it, drawn with ECharts' gauge series.
// Everything comes from the div's data attributes (measure, value, label).
// After setup the div gets controls for other code:
//   div.scoreRing.setValue(85)   update the score
// Colours come from base.css; they are read again and the ring redrawn
// whenever the theme switches (data-theme on <html>, see theme.js).
document.addEventListener("DOMContentLoaded", function () {
    var colors;

    function readColors() {
        var styles = getComputedStyle(document.documentElement);
        colors = {
            speech: styles.getPropertyValue("--speech").trim(),
            stability: styles.getPropertyValue("--stability").trim(),
            text: styles.getPropertyValue("--text").trim(),
            textMuted: styles.getPropertyValue("--text-muted").trim(),
            background: styles.getPropertyValue("--background").trim()
        };
    }
    readColors();

    var containers = document.querySelectorAll("[data-score-ring]");

    containers.forEach(function (container) {
        var label = (container.dataset.label || "").toUpperCase();
        var value = Number(container.dataset.value) || 0;
        var chart = echarts.init(container);

        // The whole ring from the current colours and value. Used on setup and
        // again when the theme switches (notMerge: replace everything).
        // Sizes scale with the ring, so a bigger ring gets a thicker ring and a bigger
        // number (at 160px: 12px ring, 40px number, 12px label).
        function draw() {
            var color = container.dataset.measure === "stability" ? colors.stability : colors.speech;
            var size = Math.min(container.clientWidth, container.clientHeight) || 160;
            chart.setOption({
                animation: false,
                series: [{
                    type: "gauge",
                    min: 0,
                    max: 100,
                    startAngle: 90,        // start at the top...
                    endAngle: -270,        // ...and go all the way round, clockwise
                    radius: "92%",
                    pointer: { show: false },
                    axisTick: { show: false },
                    splitLine: { show: false },
                    axisLabel: { show: false },
                    axisLine: { lineStyle: { width: size * 0.075, color: [[1, colors.background]] } },   // track: page background
                    progress: { show: true, roundCap: true, width: size * 0.075, itemStyle: { color: color } },
                    detail: {
                        offsetCenter: [0, "-8%"],
                        fontFamily: "Jost, sans-serif",
                        fontSize: size * 0.25,
                        fontWeight: 600,
                        color: colors.text,
                        formatter: "{value}"
                    },
                    title: {
                        offsetCenter: [0, "28%"],
                        fontFamily: "Outfit, sans-serif",
                        fontSize: Math.max(12, size * 0.075),
                        color: colors.textMuted
                    },
                    data: [{ value: value, name: label }]
                }]
            }, true);
        }
        draw();

        container.scoreRing = {
            chart: chart,
            redraw: draw,
            setValue: function (newValue) {
                value = newValue;
                chart.setOption({ series: [{ data: [{ value: value, name: label }] }] });
            }
        };

        // Redraw at the new size whenever the div changes size (and rescale the ring and text).
        new ResizeObserver(function () {
            chart.resize();
            draw();
        }).observe(container);
    });

    // Theme switch (light/dark): read the colours again and redraw every ring.
    new MutationObserver(function () {
        readColors();
        containers.forEach(function (container) {
            if (container.scoreRing) {
                container.scoreRing.redraw();
            }
        });
    }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
});
