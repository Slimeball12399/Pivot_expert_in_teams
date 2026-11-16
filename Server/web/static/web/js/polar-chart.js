// Polar chart (web/components/polar_chart.html): where the speaker leans, seen
// from above, drawn with ECharts on a square x/y plot from -max to max.
//   x: left (-) to right (+)      y: back (-) to front (+)
// Three evenly spaced rings (the outer disc in the page background, the inner
// one green), a dashed trail of the last points and the newest point as a large
// green circle with a border in the card colour.
// Everything comes from the div's data attributes (max, trail).
// After setup the div gets controls for other code:
//   div.polarChart.addPoint(lr, fb)          add the newest point
//   div.polarChart.setData([[lr, fb], ...])  replace all points
// Only the trail and the newest point are updated per point, so it keeps up
// with live data. Colours come from base.css; they are read again and the
// chart redrawn whenever the theme switches (data-theme on <html>, see theme.js).
document.addEventListener("DOMContentLoaded", function () {
    var colors;

    function readColors() {
        var styles = getComputedStyle(document.documentElement);
        colors = {
            green: styles.getPropertyValue("--green").trim(),
            stability: styles.getPropertyValue("--stability").trim(),
            line: styles.getPropertyValue("--line").trim(),
            background: styles.getPropertyValue("--background").trim(),
            backgroundRaised: styles.getPropertyValue("--background-raised").trim(),
            textMuted: styles.getPropertyValue("--text-muted").trim()
        };
    }
    readColors();

    var containers = document.querySelectorAll("[data-polar-chart]");

    containers.forEach(function (container) {
        var max = Number(container.dataset.max) || 10;
        var trail = Number(container.dataset.trail) || 40;
        var points = [];
        var chart = echarts.init(container);

        // A point further out than the outer ring is pulled in onto it, keeping its
        // direction, so the dot never leaves the plot.
        function clamp(point) {
            var lr = Number(point[0]);
            var fb = Number(point[1]);
            var distance = Math.sqrt(lr * lr + fb * fb);
            if (distance > max) {
                lr = lr * max / distance;
                fb = fb * max / distance;
            }
            return [lr, fb];
        }

        // Trail and newest point. Matched by id, so only these two series change.
        function pointSeries() {
            return [
                { id: "trail", data: points },
                { id: "latest", data: points.length ? [points[points.length - 1]] : [] }
            ];
        }

        // The whole chart from the current colours and points. Used on setup, on
        // resize and when the theme switches (notMerge: replace everything).
        // The newest dot scales with the chart (at 300px: 18px).
        function draw() {
            var size = Math.min(container.clientWidth, container.clientHeight) || 300;
            var label = { fontFamily: "Outfit, sans-serif", fontSize: 12, fill: colors.textMuted };
            var axis = {
                type: "value",
                min: -max,
                max: max,
                axisLine: { show: false },   // the cross is drawn with the rings, on top of the outer disc
                axisTick: { show: false },
                axisLabel: { show: false },
                splitLine: { show: false }
            };
            chart.setOption({
                animation: false,
                grid: { left: 24, right: 24, top: 24, bottom: 24 },   // same on every side: the plot stays square
                xAxis: axis,
                yAxis: axis,
                graphic: [
                    { type: "text", left: "center", top: 4, style: Object.assign({ text: "FRONT" }, label) },
                    { type: "text", left: "center", bottom: 4, style: Object.assign({ text: "BACK" }, label) },
                    { type: "text", left: 6, top: "middle", style: Object.assign({ text: "L" }, label) },
                    { type: "text", right: 6, top: "middle", style: Object.assign({ text: "R" }, label) }
                ],
                series: [
                    {
                        // The rings and the cross: drawn in pixels from the plot's centre, so they follow resizes.
                        type: "custom",
                        silent: true,
                        z: 1,
                        data: [[0, 0]],
                        renderItem: function (params, api) {
                            var center = api.coord([0, 0]);
                            var cx = center[0];
                            var cy = center[1];
                            var step = api.size([max / 3, 0])[0];   // one ring's width in pixels
                            var thin = { stroke: colors.line, lineWidth: 1 };
                            return {
                                type: "group",
                                children: [
                                    // outer disc in the page background, middle ring as a line
                                    { type: "circle", shape: { cx: cx, cy: cy, r: step * 3 }, style: Object.assign({ fill: colors.background }, thin) },
                                    { type: "circle", shape: { cx: cx, cy: cy, r: step * 2 }, style: Object.assign({ fill: "none" }, thin) },
                                    // the cross through the centre, edge to edge of the outer disc
                                    { type: "line", shape: { x1: cx, y1: cy - step * 3, x2: cx, y2: cy + step * 3 }, style: thin },
                                    { type: "line", shape: { x1: cx - step * 3, y1: cy, x2: cx + step * 3, y2: cy }, style: thin },
                                    // inner ring: light green fill (its own circle, so the opacity does not fade the outline) and a green outline
                                    { type: "circle", shape: { cx: cx, cy: cy, r: step }, style: { fill: colors.green, opacity: 0.14 } },
                                    { type: "circle", shape: { cx: cx, cy: cy, r: step }, style: { fill: "none", stroke: colors.green, lineWidth: 1.5 } }
                                ]
                            };
                        }
                    },
                    {
                        id: "trail",
                        type: "line",
                        silent: true,
                        z: 2,
                        symbol: "none",
                        lineStyle: { type: "dashed", width: 2, color: colors.stability },
                        data: points
                    },
                    {
                        id: "latest",
                        type: "scatter",
                        silent: true,
                        z: 3,
                        symbolSize: size * 0.06,
                        itemStyle: { color: colors.green, borderColor: colors.backgroundRaised, borderWidth: 2 },
                        data: points.length ? [points[points.length - 1]] : []
                    }
                ]
            }, true);
        }
        draw();

        container.polarChart = {
            chart: chart,
            redraw: draw,
            addPoint: function (lr, fb) {
                points.push(clamp([lr, fb]));
                if (points.length > trail) {
                    points.splice(0, points.length - trail);
                }
                chart.setOption({ series: pointSeries() });
            },
            setData: function (newPoints) {
                points = newPoints.slice(-trail).map(clamp);
                chart.setOption({ series: pointSeries() });
            }
        };

        // Redraw at the new size whenever the div changes size (and rescale the dot).
        new ResizeObserver(function () {
            chart.resize();
            draw();
        }).observe(container);
    });

    // Theme switch (light/dark): read the colours again and redraw every chart.
    new MutationObserver(function () {
        readColors();
        containers.forEach(function (container) {
            if (container.polarChart) {
                container.polarChart.redraw();
            }
        });
    }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
});
