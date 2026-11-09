// Timeline chart (web/components/timeline_chart.html): one measure over time
// with the target band, marker dots and a playhead, drawn with ECharts.
// Each [data-timeline-chart] div names the JSON script holding its config.
// After setup the div gets controls for other code (slider, transcript, live data):
//   div.timeline.setTime(seconds)          move the playhead line and dot
//   div.timeline.setData(points, markers)  replace the data (markers optional)
// Colours come from the CSS variables in base.css. They are read again and the
// chart redrawn whenever the theme switches (data-theme on <html>, see theme.js).
document.addEventListener("DOMContentLoaded", function () {
    var colors;

    function readColors() {
        var styles = getComputedStyle(document.documentElement);
        colors = {
            speech: styles.getPropertyValue("--speech").trim(),
            stability: styles.getPropertyValue("--stability").trim(),
            text: styles.getPropertyValue("--text").trim(),
            textMuted: styles.getPropertyValue("--text-muted").trim(),
            line: styles.getPropertyValue("--line").trim(),
            surface: styles.getPropertyValue("--background-raised").trim(),
            green: styles.getPropertyValue("--green").trim(),
            yellow: styles.getPropertyValue("--yellow").trim(),
            blue: styles.getPropertyValue("--blue").trim()
        };
    }
    readColors();

    var containers = document.querySelectorAll("[data-timeline-chart]");

    containers.forEach(function (container) {
        var configElement = document.getElementById(container.dataset.timelineChart);
        if (!configElement) {
            return;
        }
        var config = JSON.parse(configElement.textContent);
        var y = config.y || { min: 0, max: 100, interval: 20 };
        var points = config.points || [];
        var markers = config.markers || [];
        var currentTime = config.time === undefined ? null : config.time;
        var color;
        var chart = echarts.init(container);

        // Marker dots coloured by where they sit against the target band:
        // below yellow, inside green, above blue. Without a target they use the measure colour.
        function markerData(list) {
            return list.map(function (point) {
                var dotColor = color;
                if (config.target) {
                    dotColor = point[1] < config.target.low ? colors.yellow
                        : point[1] > config.target.high ? colors.blue
                        : colors.green;
                }
                return { value: point, itemStyle: { color: dotColor } };
            });
        }

        // The x axis shows one window of the talk at a time (config.x.window, e.g. 60 s):
        // the window the playhead is in, 0:00-1:00, 1:00-2:00, ... The last one ends at
        // the end of the recording. Without a window the whole talk is shown.
        function xRange(t) {
            var size = config.x.window || (config.x.max - config.x.min);
            var lastStart = config.x.min + Math.floor((config.x.max - config.x.min - 0.001) / size) * size;
            var start = config.x.min + Math.floor(((t === null ? config.x.min : t) - config.x.min) / size) * size;
            start = Math.max(config.x.min, Math.min(start, lastStart));
            return [start, Math.min(start + size, config.x.max)];
        }

        // markLine (vertical line) and markPoint (dot on the line) for the playhead at time t.
        function playhead(t) {
            if (t === null || points.length === 0) {
                return { markLine: { data: [] }, markPoint: { data: [] } };
            }
            // Value of the line at t: linear interpolation between the two nearest samples,
            // so the dot sits exactly on the line. Outside the data it uses the first/last value.
            var value = t <= points[0][0] ? points[0][1] : points[points.length - 1][1];
            for (var i = 0; i < points.length - 1; i++) {
                if (points[i][0] <= t && t <= points[i + 1][0]) {
                    var f = (t - points[i][0]) / (points[i + 1][0] - points[i][0]);
                    value = points[i][1] + f * (points[i + 1][1] - points[i][1]);
                    break;
                }
            }
            return {
                // The playhead line and its time pill are the x axis pointer (see draw);
                // this invisible mark line only carries the value label at the top.
                markLine: {
                    symbol: "none",
                    silent: true,
                    animation: false,
                    lineStyle: { color: "transparent" },   // not opacity 0: that hides the label too
                    data: [{
                        xAxis: t,
                        label: {
                            position: "end",
                            formatter: String(Math.round(value)),
                            color: colors.text,
                            fontWeight: "bold"
                        }
                    }]
                },
                markPoint: {
                    symbol: "circle",
                    symbolSize: 12,
                    silent: true,
                    animation: false,
                    label: { show: false },
                    itemStyle: { color: color },
                    data: [{ coord: [t, value] }]
                }
            };
        }

        // The whole chart from the current colours and data. Used on setup and
        // again when the theme switches (notMerge: replace everything).
        function draw() {
            color = config.measure === "speech" ? colors.speech : colors.stability;
            var range = xRange(currentTime);

            var lineSeries = Object.assign({
                type: "line",
                symbol: "none",
                data: points,
                lineStyle: {
                    color: color,
                    width: 2,
                    type: config.measure === "stability" ? [7, 5] : "solid"   // design system: stability is dashed
                },
                markArea: config.target ? {
                    silent: true,
                    itemStyle: { color: colors.green, opacity: 0.14 },
                    data: [[{ yAxis: config.target.low }, { yAxis: config.target.high }]]
                } : undefined
            }, playhead(currentTime));

            chart.setOption({
                animation: false,   // design system: live data stays still
                axisPointer: { triggerOn: "none" },   // the pointer is the playhead: set from code, not the mouse
                grid: { left: 8, right: 16, top: 24, bottom: 8, containLabel: true },
                xAxis: {
                    type: "value",
                    min: range[0],
                    max: range[1],
                    interval: config.x.interval,
                    // Only the inner grid: no axis line, no ticks, no grid line at the edges.
                    axisLine: { show: false },
                    axisTick: { show: false },
                    axisLabel: {
                        color: colors.textMuted,
                        fontSize: 12,
                        lineHeight: 12,   // same as the playhead pill's text, so they line up
                        margin: 8,
                        hideOverlap: true,
                        // The end label only when it is a regular tick: the last window
                        // ends at 2:42, so it would crowd 2:40.
                        showMaxLabel: (range[1] - config.x.min) % config.x.interval === 0,
                        formatter: function (s) {
                            return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
                        }
                    },
                    splitLine: { showMinLine: false, showMaxLine: false, lineStyle: { color: colors.line } },
                    // Playhead: a vertical line with the time in a pill on the same row as
                    // the other time labels, centred on the playhead.
                    axisPointer: {
                        show: currentTime !== null,
                        status: currentTime === null ? "hide" : "show",
                        value: currentTime,
                        snap: false,
                        triggerTooltip: false,
                        type: "line",
                        lineStyle: { color: colors.textMuted, width: 2, type: "solid" },   // like the design system's crosshair
                        label: {
                            show: true,
                            // Axis labels start 8px below the axis; 2.5px here + 5.5px top padding
                            // puts the pill's text on exactly the same row.
                            margin: 2.5,
                            formatter: function (params) {
                                var t = params.value;
                                return Math.floor(t / 60) + ":" + String(Math.floor(t % 60)).padStart(2, "0");
                            },
                            color: colors.surface,
                            backgroundColor: colors.text,
                            fontSize: 12,
                            lineHeight: 12,
                            // Uneven on purpose: digits sit high in their 12px line, so more
                            // space on top centres them in the 20px pill (measured).
                            padding: [5.5, 8, 2.5, 8],
                            borderRadius: 10   // 20px high, so both ends are full half circles
                        }
                    }
                },
                yAxis: {
                    type: "value",
                    min: y.min,
                    max: y.max,
                    interval: y.interval,
                    axisLine: { show: false },
                    axisTick: { show: false },
                    axisLabel: { color: colors.textMuted, fontSize: 12 },
                    splitLine: { showMinLine: false, showMaxLine: false, lineStyle: { color: colors.line } }
                },
                series: [lineSeries, {
                    type: "scatter",
                    data: markerData(markers),
                    symbol: "circle",
                    symbolSize: 8,
                    itemStyle: { color: color },
                    z: 3
                }]
            }, true);
        }
        draw();

        container.timeline = {
            chart: chart,
            redraw: draw,
            setTime: function (t) {
                currentTime = t;
                var range = xRange(t);   // switches to the next minute when the playhead crosses into it
                chart.setOption({
                    xAxis: {
                        min: range[0],
                        max: range[1],
                        axisLabel: { showMaxLabel: (range[1] - config.x.min) % config.x.interval === 0 },
                        axisPointer: { show: t !== null, status: t === null ? "hide" : "show", value: t }
                    },
                    series: [playhead(t)]   // merges into the line series only
                });
            },
            setData: function (newPoints, newMarkers) {
                points = newPoints;
                var series = [Object.assign({ data: points }, playhead(currentTime))];
                if (newMarkers) {
                    markers = newMarkers;
                    series.push({ data: markerData(markers) });
                }
                chart.setOption({ series: series });
            }
        };

        // Redraw at the new size whenever the div changes size (window resize,
        // layout changes, content appearing next to it).
        new ResizeObserver(function () {
            chart.resize();
        }).observe(container);
    });

    // Theme switch (light/dark): read the colours again and redraw every chart.
    new MutationObserver(function () {
        readColors();
        containers.forEach(function (container) {
            if (container.timeline) {
                container.timeline.redraw();
            }
        });
    }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
});
