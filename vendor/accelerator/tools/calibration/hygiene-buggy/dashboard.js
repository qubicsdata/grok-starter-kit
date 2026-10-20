// Seeded defect (H1): innerHTML assigned from interpolated user data, no escaping.
function render(el, item) {
  el.innerHTML = `<span class="type">${item.type}</span><span>${item.payload}</span>`;
}
