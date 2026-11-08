// Timeline chart (web/components/timeline_chart.html): one measure over time
// with the target band, marker dots and a playhead, drawn with ECharts.
// Each [data-timeline-chart] div names the JSON script holding its config.
// After setup the div gets controls for other code (slider, transcript, live data):
//   div.timeline.setTime(seconds)          move the playhead line and dot
//   div.timeline.setData(points, markers)  replace the data (markers optional)
// Colours come from the CSS variables in base.css, read once on page load.
document.addEventListener("DOMContentLoaded", function () {
    var styles = getComputedStyle(document.documentElement);
    var colors = {
        speech: styles.getPropertyValue("--speech").trim(),
        stability: styles.getPropertyValue("--stability").trim(),
        text: styles.getPropertyValue("--text").trim(),
        textMuted: styles.getPropertyValue("--text-muted").trim(),
        line: styles.getPropertyValue("--line").trim(),
        surface: styles.getPropertyValue("--background-raised").trim(),
        target: styles.getPropertyValue("--green").trim(),
        rangeBelow: styles.getPropertyValue("--range-below").trim(),
        rangeInside: styles.getPropertyValue("--range-inside").trim(),
        rangeAbove: styles.getPropertyValue("--range-above").trim()
    };

    document.querySelectorAll("[data-timeline-chart]").forEach(function (container) {
        var configElement = document.getElementById(container.dataset.timelineChart);
        if (!configElement) {
            return;
        }
        var config = JSON.parse(configElement.textContent);
        var color = config.measure === "speech" ? colors.speech : colors.stability;
        var y = config.y || { min: 0, max: 100, interval: 20 };
        var points = config.points || [];
        var currentTime = config.time === undefined ? null : config.time;
        var chart = echarts.init(container);

        // Marker dots coloured by where they sit against the target band:
        // below, inside or above. Without a target they use the measure colour.
        function markerData(markers) {
            return markers.map(function (point) {
                var dotColor = color;
                if (config.target) {
                    dotColor = point[1] < config.target.low ? colors.rangeBelow
                        : point[1] > config.target.high ? colors.rangeAbove
                        : colors.rangeInside;
                }
                return { value: point, itemStyle: { color: dotColor } };
            });
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
                markLine: {
                    symbol: "none",
                    silent: true,
                    animation: false,
                    lineStyle: { color: colors.text, width: 2, type: "solid" },
                    // Two lines at the same x (drawn on top of each other) so the playhead
                    // gets two labels: the time at the bottom, the value at the top.
                    data: [{
                        xAxis: t,
                        label: {
                            position: "start",
                            formatter: Math.floor(t / 60) + ":" + String(Math.floor(t % 60)).padStart(2, "0"),
                            color: colors.surface,
                            backgroundColor: colors.text,
                            padding: [2, 6],
                            borderRadius: 4
                        }
                    }, {
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
                itemStyle: { color: colors.target, opacity: 0.14 },
                data: [[{ yAxis: config.target.low }, { yAxis: config.target.high }]]
            } : undefined
        }, playhead(currentTime));

        chart.setOption({
            animation: false,   // design system: live data stays still
            grid: { left: 8, right: 16, top: 24, bottom: 8, containLabel: true },
            xAxis: {
                type: "value",
                min: config.x.min,
                max: config.x.max,
                interval: config.x.interval,
                axisLine: { lineStyle: { color: colors.line } },
                axisTick: { lineStyle: { color: colors.line } },
                axisLabel: {
                    color: colors.textMuted,
                    fontSize: 12,
                    formatter: function (s) {
                        return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
                    }
                },
                splitLine: { lineStyle: { color: colors.line } }
            },
            yAxis: {
                type: "value",
                min: y.min,
                max: y.max,
                interval: y.interval,
                axisLine: { show: true, lineStyle: { color: colors.line } },
                axisTick: { show: true, lineStyle: { color: colors.line } },
                axisLabel: { color: colors.textMuted, fontSize: 12 },
                splitLine: { lineStyle: { color: colors.line } }
            },
            series: [lineSeries, {
                type: "scatter",
                data: markerData(config.markers || []),
                symbol: "circle",
                symbolSize: 8,
                itemStyle: { color: color },
                z: 3
            }]
        });

        container.timeline = {
            chart: chart,
            setTime: function (t) {
                currentTime = t;
                chart.setOption({ series: [playhead(t)] });   // merges into the line series only
            },
            setData: function (newPoints, newMarkers) {
                points = newPoints;
                var series = [Object.assign({ data: points }, playhead(currentTime))];
                if (newMarkers) {
                    series.push({ data: markerData(newMarkers) });
                }
                chart.setOption({ series: series });
            }
        };

        window.addEventListener("resize", function () {
            chart.resize();
        });
    });
});
