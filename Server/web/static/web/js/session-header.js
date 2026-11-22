// How long a session has run, "m:ss" or "h:mm:ss", from data-started-at to
// data-ended-at; with no end yet (live) to now, every second, with "so far"
// after it unless the element has data-elapsed-plain. Every
// [data-session-elapsed] on the page: the session header
// (web/components/session_header.html) and the live session card
// (session_card.html). The times are ISO 8601 with
// their offset, so the browser's time zone doesn't matter.
document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-session-elapsed]").forEach(function (element) {
        var started = Date.parse(element.dataset.startedAt);
        var ended = element.dataset.endedAt ? Date.parse(element.dataset.endedAt) : null;

        function show() {
            var seconds = Math.max(0, Math.round(((ended || Date.now()) - started) / 1000));
            var hours = Math.floor(seconds / 3600);
            var minutes = Math.floor(seconds % 3600 / 60);
            var clock = (hours ? hours + ":" + String(minutes).padStart(2, "0") : minutes)
                + ":" + String(seconds % 60).padStart(2, "0");
            element.textContent = ended || "elapsedPlain" in element.dataset ? clock : clock + " so far";
        }

        show();
        if (!ended) {
            setInterval(show, 1000);
        }
    });
});
