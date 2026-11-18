// Menu button in the header (below 680px the nav links only show as a menu).
// Opens and closes the nav by setting data-nav-open on the header. Closes on
// Escape, on a click outside the header, and when the screen grows wide again.
document.addEventListener("DOMContentLoaded", function () {
    var button = document.querySelector("[data-nav-toggle]");
    if (!button) {
        return;
    }
    var header = button.closest(".site-header");

    function setOpen(open) {
        header.toggleAttribute("data-nav-open", open);
        button.setAttribute("aria-expanded", String(open));
        button.setAttribute("aria-label", open ? "Close menu" : "Menu");
    }

    button.addEventListener("click", function () {
        setOpen(!header.hasAttribute("data-nav-open"));
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && header.hasAttribute("data-nav-open")) {
            setOpen(false);
            button.focus();
        }
    });

    document.addEventListener("click", function (event) {
        if (!header.contains(event.target)) {
            setOpen(false);
        }
    });

    window.matchMedia("(min-width: 680px)").addEventListener("change", function (event) {
        if (event.matches) {
            setOpen(false);
        }
    });
});
