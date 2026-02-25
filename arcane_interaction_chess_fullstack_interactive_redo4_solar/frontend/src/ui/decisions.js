function esc(s) {
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

export class DecisionModal {
  constructor(rootDoc) {
    this.root = rootDoc;
    this.modal = rootDoc.querySelector("#decisionModal");
    this.promptEl = rootDoc.querySelector("#decisionPrompt");
    this.ctxEl = rootDoc.querySelector("#decisionContext");
    this.optsEl = rootDoc.querySelector("#decisionOptions");
    this.btnCancel = rootDoc.querySelector("#btnDecisionCancel");

    this._onPick = null;
    this._onCancel = null;

    this.btnCancel.addEventListener("click", () => {
      if (this._onCancel) this._onCancel();
    });
  }

  show(pending, { onPick, onCancel } = {}) {
    this._onPick = onPick || null;
    this._onCancel = onCancel || null;

    this.modal.hidden = false;
    this.promptEl.textContent = pending.prompt || "Decision";

    const ctx = pending.context || {};
    const lines = [];
    if (pending.kind) lines.push(`kind: ${pending.kind}`);
    if (ctx.side) lines.push(`side: ${ctx.side}`);
    if (ctx.rewind_plies != null) lines.push(`rewind plies: ${ctx.rewind_plies}`);
    if (ctx.forbidden_uci) lines.push(`forbidden: ${ctx.forbidden_uci}`);
    if (ctx.mover_uid != null) lines.push(`piece uid: ${ctx.mover_uid}`);
    if (ctx.spent_uid != null) lines.push(`spent uid: ${ctx.spent_uid}`);
    if (Array.isArray(ctx.undone_uci) && ctx.undone_uci.length) {
      lines.push(`undone: ${ctx.undone_uci.join(" ")}`);
    }
    this.ctxEl.textContent = lines.join("\n");

    // Redo replay can't be meaningfully cancelled (the timeline is already rewound),
    // so hide the cancel button for that prompt.
    this.btnCancel.hidden = (pending.kind === "redo_replay");

    this.optsEl.innerHTML = "";
    const opts = pending.options || [];
    for (const o of opts) {
      const row = document.createElement("div");
      row.className = "opt";
      const label = o.label != null ? String(o.label) : String(o.id);
      const meta = [];
      if (o.type) meta.push(o.type);
      if (o.uid != null) meta.push(`uid:${o.uid}`);
      if (o.to_alg) meta.push(`to:${o.to_alg}`);
      row.innerHTML = `<div><div class="label">${esc(label)}</div><div class="meta">${esc(meta.join(" • "))}</div></div>`;
      const btn = document.createElement("button");
      btn.className = "btn btn-primary";
      btn.textContent = "Select";
      btn.addEventListener("click", () => {
        if (this._onPick) this._onPick(o.id);
      });
      row.appendChild(btn);
      this.optsEl.appendChild(row);
    }
  }

  hide() {
    this.modal.hidden = true;
    this.optsEl.innerHTML = "";
    this.ctxEl.textContent = "";
    this.btnCancel.hidden = false;
    this._onPick = null;
    this._onCancel = null;
  }
}
