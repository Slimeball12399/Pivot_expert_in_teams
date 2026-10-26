// Show/hide password buttons from the input component (reveal=True).
// The button's data-password-toggle holds the id of its input.
document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-password-toggle]").forEach(function (button) {
        var input = document.getElementById(button.dataset.passwordToggle);
        if (!input) {
            return;
        }
        button.addEventListener("click", function () {
            var show = input.type === "password";
            input.type = show ? "text" : "password";
            button.setAttribute("aria-pressed", String(show));
            button.setAttribute("aria-label", show ? "Hide password" : "Show password");
        });
    });
});
