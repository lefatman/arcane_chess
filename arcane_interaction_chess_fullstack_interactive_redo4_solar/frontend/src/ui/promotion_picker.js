function esc(s) {
  return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

const PROMOTION_ORDER = ["q", "r", "b", "n"];
const PROMOTION_LABELS = {
  q: "Queen",
  r: "Rook",
  b: "Bishop",
  n: "Knight",
};

function promotionRank(move) {
  const promoteTo = move && move.promote_to != null ? String(move.promote_to).toLowerCase() : "";
  const idx = PROMOTION_ORDER.indexOf(promoteTo);
  return idx >= 0 ? idx : PROMOTION_ORDER.length;
}

function normalizedPromotion(move) {
  const promoteTo = move && move.promote_to != null ? String(move.promote_to).toLowerCase() : "";
  return PROMOTION_LABELS[promoteTo] || null;
}

export class PromotionPicker {
  constructor(doc) {
    this.doc = doc;
    this.modal = doc.querySelector("#promotionModal");
    this.optionsEl = doc.querySelector("#promotionOptions");
    this.promptEl = doc.querySelector("#promotionPrompt");
    this.btnCancel = doc.querySelector("#btnPromotionCancel");
    this._onPick = null;
    this._onCancel = null;

    this.btnCancel.addEventListener("click", () => {
      if (this._onCancel) this._onCancel();
      this.hide();
    });
  }

  show(moves, { getLabel, onPick, onCancel } = {}) {
    this._onPick = onPick || null;
    this._onCancel = onCancel || null;
    this.optionsEl.innerHTML = "";

    const entries = [];
    for (let i = 0; i < moves.length; i += 1) {
      const move = moves[i];
      const fallback = getLabel ? String(getLabel(move)) : "Choose";
      const promo = normalizedPromotion(move);
      const variantTag = `variant ${i + 1}`;
      const meta = promo ? `${fallback} • ${variantTag}` : `${fallback} • ${variantTag}`;
      entries.push({
        idx: i,
        move,
        rank: promotionRank(move),
        label: promo || fallback,
        meta,
      });
    }
    entries.sort((a, b) => {
      if (a.rank !== b.rank) return a.rank - b.rank;
      return a.idx - b.idx;
    });

    for (const entry of entries) {
      const row = document.createElement("div");
      row.className = "opt";
      row.innerHTML = `<div><div class="label">${esc(entry.label)}</div><div class="meta">${esc(entry.meta)}</div></div>`;

      const btn = document.createElement("button");
      btn.className = "btn btn-primary";
      btn.textContent = "Select";
      btn.addEventListener("click", () => {
        if (this._onPick) this._onPick(entry.move);
        this.hide();
      });
      row.appendChild(btn);
      this.optionsEl.appendChild(row);
    }

    this.promptEl.textContent = entries.length && entries[0].rank < PROMOTION_ORDER.length ? "Choose promotion" : "Choose move variant";
    this.modal.hidden = false;
  }

  hide() {
    this.modal.hidden = true;
    this.optionsEl.innerHTML = "";
    this._onPick = null;
    this._onCancel = null;
  }
}
