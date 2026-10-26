// Theme: "system" (follow the OS setting), "light" or "dark".
// The toggle button cycles System -> Light -> Dark -> System. The choice is saved
// in the browser; "system" saves nothing, so the OS setting is followed again.
//
// On <html> it sets:
//   data-theme="light|dark"            -> which colours the CSS uses
//   data-theme-choice="system|light|dark" -> which icon the toggle shows
(function () {
    var STORAGE_KEY = "pivot-theme";
    var ORDER = ["system", "light", "dark"];
    var LABELS = { system: "Theme: System", light: "Theme: Light", dark: "Theme: Dark" };
    var root = document.documentElement;
    var media = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;

    function getChoice() {
        try {
            var saved = localStorage.getItem(STORAGE_KEY);
            return saved === "light" || saved === "dark" ? saved : "system";
        } catch (e) {
            return "system"; // storage blocked, e.g. private mode
        }
    }

    function saveChoice(choice) {
        try {
            if (choice === "system") {
                localStorage.removeItem(STORAGE_KEY);
            } else {
                localStorage.setItem(STORAGE_KEY, choice);
            }
        } catch (e) {
            // Can't save: the choice just lasts until the page is reloaded.
        }
    }

    function systemTheme() {
        return media && media.matches ? "dark" : "light";
    }

    var choice = getChoice();

    function apply() {
        root.setAttribute("data-theme", choice === "system" ? systemTheme() : choice);
        root.setAttribute("data-theme-choice", choice);
        document.querySelectorAll("[data-theme-toggle]").forEach(function (button) {
            button.setAttribute("aria-label", LABELS[choice]);
            button.setAttribute("title", LABELS[choice]);
        });
    }

    // Runs in <head>, before the body is drawn.
    apply();

    document.addEventListener("DOMContentLoaded", function () {
        apply();

        document.querySelectorAll("[data-theme-toggle]").forEach(function (button) {
            button.addEventListener("click", function () {
                choice = ORDER[(ORDER.indexOf(choice) + 1) % ORDER.length];
                saveChoice(choice);
                apply();
            });
        });

        // In "system" mode, follow the OS when it switches (e.g. at sunset).
        if (media) {
            media.addEventListener("change", function () {
                if (choice === "system") {
                    apply();
                }
            });
        }
    });
})();
