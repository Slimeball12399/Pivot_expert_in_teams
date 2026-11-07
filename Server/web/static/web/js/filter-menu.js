// Filter menus (web/components/filter_menu.html). The Filters button opens a
// panel of tag groups. In a group with data-multiple="false" picking a tag
// unselects the others (one per group, and one always stays selected); with
// "true" each tag turns on and off by itself.
//
// The panel closes with the button, its cross, Escape or a click outside. Closing it
// redraws the selected tags next to the button and fires a "filtermenu:apply" event on the menu, with the selected values per
// group in event.detail, e.g. {status: ["active"]}, and, when the selection
// changed, reloads the page with it in the URL (?status=active), keeping the
// other parameters such as the search.
document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-filter-menu]").forEach(function (menu) {
        var button = menu.querySelector("[data-filter-menu-toggle]");
        var panel = document.getElementById(button.getAttribute("aria-controls"));
        var chips = menu.querySelector("[data-filter-chips]");

        function drawChips() {
            chips.replaceChildren();
            menu.querySelectorAll(".filter-tag[aria-pressed=true]").forEach(function (tag) {
                var chip = document.createElement("li");
                chip.className = "filter-chip";
                chip.textContent = tag.textContent.trim();
                chips.append(chip);
            });
        }

        function selection() {
            var result = {};
            menu.querySelectorAll("[data-filter-group]").forEach(function (group) {
                result[group.dataset.filterGroup] = Array.from(
                    group.querySelectorAll(".filter-tag[aria-pressed=true]"),
                    function (tag) { return tag.dataset.value; });
            });
            return result;
        }

        // Reload only when the selection differs from the one the page was drawn with.
        function applyToUrl(selected) {
            if (JSON.stringify(selected) === initial) {
                return;
            }
            var params = new URLSearchParams(window.location.search);
            Object.keys(selected).forEach(function (name) {
                params.delete(name);
                selected[name].forEach(function (value) { params.append(name, value); });
            });
            window.location.search = params.toString();
        }

        function setOpen(open) {
            if (open === !panel.hidden) {
                return;
            }
            panel.hidden = !open;
            button.setAttribute("aria-expanded", String(open));
            if (!open) {
                drawChips();
                var selected = selection();
                menu.dispatchEvent(new CustomEvent("filtermenu:apply", {detail: selected}));
                applyToUrl(selected);
            }
        }

        var initial = JSON.stringify(selection());

        button.addEventListener("click", function () {
            setOpen(panel.hidden);
        });

        menu.querySelector("[data-filter-menu-close]").addEventListener("click", function () {
            setOpen(false);
            button.focus();
        });

        menu.querySelectorAll("[data-filter-group]").forEach(function (group) {
            var multiple = group.dataset.multiple === "true";
            group.querySelectorAll(".filter-tag").forEach(function (tag) {
                tag.addEventListener("click", function () {
                    if (multiple) {
                        var pressed = tag.getAttribute("aria-pressed") === "true";
                        tag.setAttribute("aria-pressed", String(!pressed));
                        return;
                    }
                    group.querySelectorAll(".filter-tag").forEach(function (other) {
                        other.setAttribute("aria-pressed", String(other === tag));
                    });
                });
            });
        });

        document.addEventListener("keydown", function (event) {
            if (event.key === "Escape" && !panel.hidden) {
                setOpen(false);
                button.focus();
            }
        });

        document.addEventListener("click", function (event) {
            if (!menu.contains(event.target)) {
                setOpen(false);
            }
        });
    });
});
