"use strict";
document.addEventListener("DOMContentLoaded", () => {
  // ---- ⌘K command palette ----
  const modal = document.getElementById("cmdk");
  const bodyTmpl = document.getElementById("cmdk-body");
  function openCmdk() {
    if (!modal || !bodyTmpl) return;
    const body = modal.querySelector(".modal-body");
    if (body && !body.dataset.loaded) {
      body.appendChild(bodyTmpl.content.cloneNode(true));
      body.dataset.loaded = "1";
      if (window.htmx) window.htmx.process(body);
    }
    modal.hidden = false;
    const input = modal.querySelector("input[name=q]");
    if (input) input.focus();
  }
  function closeCmdk() { if (modal) modal.hidden = true; }
  document.querySelectorAll("[data-cmdk]").forEach((b) => b.addEventListener("click", openCmdk));
  document.addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); openCmdk(); }
    if (e.key === "Escape") closeCmdk();
  });
  if (modal) modal.querySelectorAll("[data-close]").forEach((el) => el.addEventListener("click", closeCmdk));

  // ---- tap-to-tally ----
  const grid = document.querySelector(".tally-grid");
  if (grid) {
    const counts = {};
    grid.querySelectorAll(".tally-tile").forEach((tile) => {
      tile.addEventListener("click", () => {
        const id = tile.dataset.variation;
        counts[id] = (counts[id] || 0) + 1;
        const badge = tile.querySelector(".tally-count");
        badge.dataset.count = counts[id];
        badge.textContent = counts[id];
      });
    });
    const done = document.querySelector("[data-tally-commit]");
    if (done) {
      done.addEventListener("click", () => {
        const channel = grid.dataset.channel || done.dataset.channel || "";
        const session = Object.entries(counts)
          .filter(([, n]) => n > 0)
          .map(([variation_id, quantity]) => {
            const tile = grid.querySelector(`.tally-tile[data-variation="${variation_id}"]`);
            return { variation_id, channel_id: channel, quantity,
                     unit_price: parseFloat(tile.dataset.price) };
          });
        const form = new FormData();
        form.append("session", JSON.stringify(session));
        fetch(done.dataset.tallyCommit, { method: "POST", body: form })
          .then((r) => r.text()).then((html) => {
            const target = document.getElementById("market-lines");
            if (target) target.outerHTML = html;
          });
      });
    }
  }

  // ---- progressive collapse: a singular <details> opens by default (handled in templates) ----
});

// NL capture: serialize confirm rows -> one JSON POST to /capture/commit
document.addEventListener('click', (e) => {
  const btn = e.target.closest('[data-capture-submit]');
  if (!btn) return;
  const form = btn.closest('[data-capture-commit]');
  if (!form) return;
  const lines = [...form.querySelectorAll('[data-capture-line]')].map((row) => ({
    variation_id: row.dataset.variation,
    quantity: row.querySelector('[name="quantity"]').value,
    unit_price: row.querySelector('[name="unit_price"]').value || row.querySelector('[name="quantity"]').dataset.price || '0',
  }));
  const body = new URLSearchParams({ lines: JSON.stringify(lines) });
  fetch(form.dataset.captureCommit, { method: 'POST', body })
    .then((r) => r.text())
    .then((html) => {
      const lm = document.querySelector('#market-lines');
      if (lm) lm.outerHTML = html;
      form.innerHTML = '<p class="muted">Recorded.</p>';
    });
});
