// Toasts (web/components/toasts.html): each closes with its cross, and by
// itself after a few seconds unless the mouse is over it.
document.addEventListener("DOMContentLoaded", function () {
    var LIFETIME_MS = 6000;

    document.querySelectorAll("[data-toast]").forEach(function (toast) {
        var timer = setTimeout(close, LIFETIME_MS);

        function close() {
            clearTimeout(timer);
            var stack = toast.parentElement;
            toast.remove();
            if (stack && !stack.children.length) {
                stack.remove();
            }
        }

        toast.querySelector("[data-toast-close]").addEventListener("click", close);
        toast.addEventListener("mouseenter", function () { clearTimeout(timer); });
        toast.addEventListener("mouseleave", function () { timer = setTimeout(close, LIFETIME_MS); });
    });
});
