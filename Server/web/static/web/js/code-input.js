// One-time code boxes from the code input component (code_input.html).
// Typing a digit moves to the next box, Backspace on an empty box goes back,
// the arrow keys move between boxes, and pasting or autofilling the whole
// code (autocomplete="one-time-code") spreads it over the boxes.
document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-code-input]").forEach(function (field) {
        var boxes = Array.prototype.slice.call(field.querySelectorAll(".code-box"));

        // Writes the digits in text into the boxes from index start on,
        // then focuses the box after the last one written.
        function fill(start, text) {
            var digits = text.replace(/\D/g, "").split("");
            if (digits.length >= boxes.length) {
                start = 0;  // the whole code: always start at the first box
            }
            var i = start;
            digits.forEach(function (digit) {
                if (i < boxes.length) {
                    boxes[i].value = digit;
                    i++;
                }
            });
            boxes[Math.min(i, boxes.length - 1)].focus();
        }

        boxes.forEach(function (box, index) {
            box.addEventListener("focus", function () {
                box.select();
            });

            box.addEventListener("input", function (event) {
                // Typing: only the key just pressed. Autofill: the whole value.
                var text = event.inputType === "insertText" && event.data ? event.data : box.value;
                box.value = "";
                fill(index, text);
            });

            box.addEventListener("keydown", function (event) {
                if (event.key === "Backspace" && box.value === "" && index > 0) {
                    event.preventDefault();
                    boxes[index - 1].value = "";
                    boxes[index - 1].focus();
                } else if (event.key === "ArrowLeft" && index > 0) {
                    event.preventDefault();
                    boxes[index - 1].focus();
                } else if (event.key === "ArrowRight" && index < boxes.length - 1) {
                    event.preventDefault();
                    boxes[index + 1].focus();
                }
            });

            box.addEventListener("paste", function (event) {
                event.preventDefault();
                fill(index, (event.clipboardData || window.clipboardData).getData("text"));
            });
        });
    });
});
