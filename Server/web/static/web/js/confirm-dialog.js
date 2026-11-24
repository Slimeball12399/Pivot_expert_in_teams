// Confirm dialog (web/components/confirm_dialog.html), one per page.
//
// Any button with data-confirm-url opens it, with its data-confirm-title,
// -body and -label (default "Delete"). The red button sends
// data-confirm-method (default DELETE) to data-confirm-url with the CSRF
// token in the X-CSRFToken header. A 2xx answer reloads the page (the view's
// toast shows then); an error shows in the dialog, which stays open. Closes
// with Escape, Cancel, the cross or a click on the backdrop.
document.addEventListener("DOMContentLoaded", function () {
    var dialog = document.getElementById("confirm-dialog");
    if (!dialog) {
        return;
    }
    var form = dialog.querySelector("form");
    var title = document.getElementById("confirm-dialog-title");
    var body = document.getElementById("confirm-dialog-body");
    var error = document.getElementById("confirm-dialog-error");
    var confirm = document.getElementById("confirm-dialog-confirm");
    var token = form.querySelector("[name=csrfmiddlewaretoken]").value;
    var request = null;  // {url, method} of the button that opened it

    function showError(message) {
        error.textContent = message;
        error.hidden = false;
    }

    document.querySelectorAll("[data-confirm-url]").forEach(function (button) {
        button.addEventListener("click", function () {
            request = {
                url: button.dataset.confirmUrl,
                method: button.dataset.confirmMethod || "DELETE",
            };
            title.textContent = button.dataset.confirmTitle || "Are you sure?";
            body.textContent = button.dataset.confirmBody || "";
            confirm.textContent = button.dataset.confirmLabel || "Delete";
            error.hidden = true;
            dialog.showModal();
            // Cancel first: the safe choice gets the focus.
            document.getElementById("confirm-dialog-cancel").focus();
        });
    });

    form.addEventListener("submit", function (event) {
        event.preventDefault();
        error.hidden = true;
        confirm.disabled = true;
        fetch(request.url, {
            method: request.method,
            headers: {"X-CSRFToken": token, "Accept": "application/json"},
        })
            .then(function (response) {
                if (response.ok) {
                    window.location.reload();
                    return;
                }
                return response.json().catch(function () {
                    return {};
                }).then(function (data) {
                    var errors = data.errors || {};
                    showError((errors.__all__ || ["That didn't work. Reload the page and try again."])[0]);
                    confirm.disabled = false;
                });
            })
            .catch(function () {
                showError("That didn't work. Check your connection and try again.");
                confirm.disabled = false;
            });
    });

    dialog.querySelectorAll("[data-dialog-close], #confirm-dialog-cancel").forEach(function (button) {
        button.addEventListener("click", function () {
            dialog.close();
        });
    });

    // A click on the dialog element itself is a click on the backdrop.
    dialog.addEventListener("click", function (event) {
        if (event.target === dialog) {
            dialog.close();
        }
    });

    dialog.addEventListener("close", function () {
        confirm.disabled = false;
        request = null;
    });
});
