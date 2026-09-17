"use strict";

document.addEventListener("focusin", (event) => {
    if (event.target.matches(".short-url-widget input")) {
        event.target.select();
    }
});

document.addEventListener("click", async (event) => {
    const button = event.target.closest(".short-url-copy");
    if (!button) return;

    const widget = button.closest(".short-url-widget");
    const input = widget.querySelector("input");
    const status = widget.querySelector(".short-url-copy-status");
    button.disabled = true;
    status.textContent = "";

    try {
        if (!navigator.clipboard?.writeText) {
            throw new Error("Clipboard unavailable");
        }
        await navigator.clipboard.writeText(input.value);
        status.textContent = "Copied!";
    } catch {
        input.focus();
        input.select();
        status.textContent = "Copy failed. Copy the selected URL manually.";
    } finally {
        button.disabled = false;
    }
});
