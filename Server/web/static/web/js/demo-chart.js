// Demo page chart (/demo/). ECharts "Get started" example:
// https://echarts.apache.org/handbook/en/get-started/
// ECharts itself is loaded from the CDN in demo.html.
document.addEventListener("DOMContentLoaded", function () {
    var container = document.getElementById("main");
    if (!container) {
        return;
    }
    var myChart = echarts.init(container);

    // Fake data: one value every 0.5 s for a 60 s talk.
    var data = [];
    for (var t = 0; t <= 60; t += 0.5) {
        data.push([t, 60 + Math.round(15 * Math.sin(t / 5) + Math.random() * 6)]);
    }

    // Fake markers: ~8 random points taken from the data, so they sit on the line.
    // Later the server sends these (peaks and minimums computed between talks).
    var markers = data.filter(function () { return Math.random() < 8 / data.length; });

    // Playhead: fixed at 35 s for now. Later this comes from the slider / transcript / live data.
    var playheadTime = 35;
    // Value of the line at the playhead (linear interpolation between the two nearest samples),
    // so the playhead dot sits exactly on the line.
    var playheadValue = data[data.length - 1][1];
    for (var i = 0; i < data.length - 1; i++) {
        if (data[i][0] <= playheadTime && playheadTime <= data[i + 1][0]) {
            var f = (playheadTime - data[i][0]) / (data[i + 1][0] - data[i][0]);
            playheadValue = data[i][1] + f * (data[i + 1][1] - data[i][1]);
            break;
        }
    }

    myChart.setOption({
        xAxis: {
            type: "value",
            min: 0,
            max: 60,
            interval: 10,
            axisLabel: {
                formatter: function (s) {
                    return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
                },
            },
        },
        yAxis: {
            type: "value",
            min: 0,
            max: 100
        },
        series: [{
            type: "line",
            symbol: "none",
            data: data,
            // Target range band: belongs to the series, not the top level of the option.
            markArea: {
                silent: false,
                itemStyle: { color: "rgba(3, 255, 129, 0.14)" },
                data: [[{ yAxis: 40 }, { yAxis: 60 }]]
            },
            // Playhead: vertical line at the current time...
            markLine: {
                symbol: "none",
                silent: true,
                animation: false,
                lineStyle: { color: "#123048", width: 2, type: "solid" },
                label: {
                    formatter: function () {
                        return Math.floor(playheadTime / 60) + ":" + String(Math.floor(playheadTime % 60)).padStart(2, "0");
                    }
                },
                data: [{ xAxis: playheadTime }]
            },
            // ...and a dot where it crosses the line.
            markPoint: {
                symbol: "circle",
                symbolSize: 12,
                silent: true,
                animation: false,
                label: { show: false },
                itemStyle: { color: "#85356E", borderColor: "#FFFFFF", borderWidth: 2 },
                data: [{ coord: [playheadTime, playheadValue] }]
            }
        }, {
            // Marker dots on top of the line.
            type: "scatter",
            data: markers,
            symbol: "circle",
            symbolSize: 8,
            itemStyle: { color: "#85356E", borderColor: "#FFFFFF", borderWidth: 2 },
            z: 3
        }]
    }
    );

    window.addEventListener("resize", function () {
        myChart.resize();
    });
});
