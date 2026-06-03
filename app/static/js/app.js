/* DAP — interactions front (vanilla JS) */
(function () {
  "use strict";

  // ---- Toasts ----
  function toast(msg, type) {
    const c = document.getElementById("toast-container");
    if (!c) return;
    const el = document.createElement("div");
    el.className = "toast " + (type || "info");
    const icon = { success: "check-circle", error: "x-circle",
                   warning: "alert-triangle", info: "info" }[type] || "info";
    el.innerHTML = '<i data-lucide="' + icon + '"></i><span></span>';
    el.querySelector("span").textContent = msg;
    c.appendChild(el);
    if (window.lucide) lucide.createIcons();
    setTimeout(() => { el.style.opacity = "0"; setTimeout(() => el.remove(), 300); }, 3800);
  }
  window.dapToast = toast;

  document.querySelectorAll(".toast-mount").forEach((m) => {
    toast(m.dataset.msg, m.dataset.type);
  });

  // ---- Dropdowns ----
  function setupDropdown(wrapperId, btnId) {
    const wrap = document.getElementById(wrapperId);
    if (!wrap) return;
    const btn = document.getElementById(btnId);
    const menu = wrap.querySelector(".dropdown-menu");
    if (!btn || !menu) return;
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      document.querySelectorAll(".dropdown-menu").forEach((m) => { if (m !== menu) m.hidden = true; });
      menu.hidden = !menu.hidden;
    });
  }
  setupDropdown("notifDropdown", "notifBtn");
  setupDropdown("roleDropdown", "roleBtn");
  setupDropdown("avatarDropdown", "avatarBtn");
  document.addEventListener("click", () => {
    document.querySelectorAll(".dropdown-menu").forEach((m) => (m.hidden = true));
  });

  // ---- Sidebar mobile ----
  const sidebar = document.getElementById("sidebar");
  const backdrop = document.getElementById("sidebarBackdrop");
  const toggle = document.getElementById("sidebarToggle");
  if (toggle) {
    toggle.addEventListener("click", () => {
      sidebar.classList.toggle("open");
      backdrop.classList.toggle("show");
    });
    backdrop.addEventListener("click", () => {
      sidebar.classList.remove("open");
      backdrop.classList.remove("show");
    });
  }

  // ---- Global search ----
  const search = document.getElementById("globalSearch");
  const panel = document.getElementById("searchPanel");
  if (search && panel) {
    let t = null;
    const statusLabel = (s) => s.replaceAll("_", " ").toLowerCase();
    search.addEventListener("input", () => {
      clearTimeout(t);
      const q = search.value.trim();
      if (q.length < 2) { panel.hidden = true; return; }
      t = setTimeout(async () => {
        const r = await fetch("/search?q=" + encodeURIComponent(q));
        const d = await r.json();
        let html = "";
        if (d.daps.length) {
          html += '<div class="search-group-title">DAP</div>';
          d.daps.forEach((x) => {
            html += '<a class="search-result" href="/daps/' + x.id + '"><strong>' +
              x.reference + "</strong> — " + statusLabel(x.statut) + "</a>";
          });
        }
        if (d.pieces.length) {
          html += '<div class="search-group-title">Pièces</div>';
          d.pieces.forEach((x) => {
            html += '<div class="search-result"><strong>' + x.code + "</strong> — " + x.designation + "</div>";
          });
        }
        if (d.users && d.users.length) {
          html += '<div class="search-group-title">Utilisateurs</div>';
          d.users.forEach((x) => {
            html += '<div class="search-result"><strong>' + x.nom + "</strong> — " + x.email + "</div>";
          });
        }
        if (!html) html = '<div class="search-empty">Aucun résultat</div>';
        panel.innerHTML = html;
        panel.hidden = false;
      }, 220);
    });
    document.addEventListener("click", (e) => {
      if (!panel.contains(e.target) && e.target !== search) panel.hidden = true;
    });
    document.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault(); search.focus();
      }
    });
  }

  // ---- Modal helper ----
  window.dapModal = function (opts) {
    const root = document.getElementById("modal-root");
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    overlay.innerHTML =
      '<div class="modal"><div class="modal-head"><i data-lucide="' + (opts.icon || "help-circle") +
      '"></i>' + opts.title + "</div><div class=\"modal-body\">" + (opts.body || "") +
      '</div><div class="modal-foot"><button class="btn btn-ghost" data-close>Annuler</button>' +
      '<button class="btn ' + (opts.confirmClass || "btn-primary") + '" data-confirm>' +
      (opts.confirmLabel || "Confirmer") + "</button></div></div>";
    root.appendChild(overlay);
    if (window.lucide) lucide.createIcons();
    const close = () => overlay.remove();
    overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });
    overlay.querySelector("[data-close]").addEventListener("click", close);
    overlay.querySelector("[data-confirm]").addEventListener("click", () => {
      if (opts.onConfirm) opts.onConfirm(overlay);
      if (!opts.keepOpen) close();
    });
    return overlay;
  };

  // ---- Action with optional motif (reject / rupture / complement) ----
  document.querySelectorAll("[data-action-form]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const action = btn.dataset.action;
      const url = btn.dataset.url;
      const needsMotif = btn.dataset.motif === "1";
      const label = btn.dataset.label || "Confirmer";
      const body = needsMotif
        ? '<div class="field"><label>Motif / message</label><textarea id="motifInput" placeholder="Saisir le motif…"></textarea></div>'
        : "<p>Confirmer l'action « " + label + " » ?</p>";
      window.dapModal({
        title: label, icon: "alert-circle", body: body, confirmLabel: label,
        confirmClass: btn.dataset.confirmClass || "btn-primary",
        keepOpen: needsMotif,
        onConfirm: (overlay) => {
          let motif = "";
          if (needsMotif) {
            motif = overlay.querySelector("#motifInput").value.trim();
            if (!motif) { toast("Un motif est requis.", "error"); return; }
            overlay.remove();
          }
          const f = document.createElement("form");
          f.method = "post"; f.action = url;
          f.innerHTML = '<input name="action" value="' + action + '">' +
            '<input name="motif" value="">';
          f.querySelector('input[name=motif]').value = motif;
          document.body.appendChild(f); f.submit();
        },
      });
    });
  });

  // ---- Confirm simple ----
  document.querySelectorAll("[data-confirm-submit]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const form = btn.closest("form");
      window.dapModal({
        title: btn.dataset.title || "Confirmer", icon: "alert-triangle",
        body: "<p>" + (btn.dataset.message || "Confirmer cette action ?") + "</p>",
        confirmClass: btn.dataset.confirmClass || "btn-danger",
        onConfirm: () => form.submit(),
      });
    });
  });

  // ---- Kanban drag & drop ----
  const board = document.getElementById("kanbanBoard");
  if (board) {
    let dragged = null;
    board.querySelectorAll(".kanban-card").forEach((card) => {
      card.addEventListener("dragstart", () => { dragged = card; card.classList.add("dragging"); });
      card.addEventListener("dragend", () => { card.classList.remove("dragging"); dragged = null; });
    });
    board.querySelectorAll(".kanban-col").forEach((col) => {
      col.addEventListener("dragover", (e) => { e.preventDefault(); col.classList.add("drag-over"); });
      col.addEventListener("dragleave", () => col.classList.remove("drag-over"));
      col.addEventListener("drop", async (e) => {
        e.preventDefault();
        col.classList.remove("drag-over");
        if (!dragged) return;
        const dapId = dragged.dataset.id;
        const target = col.dataset.statut;
        const from = dragged.dataset.statut;
        if (from === target) return;
        try {
          const r = await fetch("/stock/move", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ dap_id: dapId, target: target }),
          });
          const d = await r.json();
          if (d.redirect) { window.location = d.redirect; return; }
          if (d.ok) { window.location.reload(); }
          else { toast(d.error || "Déplacement refusé.", "error"); }
        } catch (err) { toast("Erreur réseau.", "error"); }
      });
    });
  }

  // ---- Signature pad ----
  const pad = document.getElementById("sigPad");
  if (pad) {
    const ctx = pad.getContext("2d");
    function resize() {
      const r = pad.getBoundingClientRect();
      pad.width = r.width; pad.height = r.height;
      ctx.lineWidth = 2.2; ctx.lineCap = "round"; ctx.strokeStyle = "#1E293B";
    }
    resize(); window.addEventListener("resize", resize);
    let drawing = false, dirty = false;
    const pos = (e) => {
      const r = pad.getBoundingClientRect();
      const p = e.touches ? e.touches[0] : e;
      return { x: p.clientX - r.left, y: p.clientY - r.top };
    };
    const start = (e) => { drawing = true; const p = pos(e); ctx.beginPath(); ctx.moveTo(p.x, p.y); };
    const move = (e) => { if (!drawing) return; e.preventDefault(); const p = pos(e); ctx.lineTo(p.x, p.y); ctx.stroke(); dirty = true; };
    const end = () => { drawing = false; };
    pad.addEventListener("mousedown", start); pad.addEventListener("mousemove", move);
    window.addEventListener("mouseup", end);
    pad.addEventListener("touchstart", start); pad.addEventListener("touchmove", move, { passive: false });
    pad.addEventListener("touchend", end);
    const clearBtn = document.getElementById("sigClear");
    if (clearBtn) clearBtn.addEventListener("click", () => { ctx.clearRect(0, 0, pad.width, pad.height); dirty = false; });
    const form = pad.closest("form");
    if (form) form.addEventListener("submit", () => {
      const input = document.getElementById("signatureInput");
      if (input && dirty) input.value = pad.toDataURL("image/png");
    });
  }

  // ---- Filter chips toggle (visual) ----
  document.querySelectorAll(".chip input").forEach((cb) => {
    const chip = cb.closest(".chip");
    if (cb.checked) chip.classList.add("active");
    cb.addEventListener("change", () => chip.classList.toggle("active", cb.checked));
  });
})();
