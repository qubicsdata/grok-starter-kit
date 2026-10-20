// Hygienic DOM rendering: every interpolated value is escaped before innerHTML.
function escHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function render(el, item) {
  el.innerHTML = `<span class="type">${escHtml(item.type)}</span>`;
}
