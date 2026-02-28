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

    const sorted = [...moves].sort((a, b) => {
      const pa = promotionRank(a);
      const pb = promotionRank(b);
      if (pa !== pb) return pa - pb;
      return String(getLabel ? getLabel(a) : "").localeCompare(String(getLabel ? getLabel(b) : ""));
    });

    for (const move of sorted) {
      const row = document.createElement("div");
      row.className = "opt";
      const promo = normalizedPromotion(move);
      const fallback = getLabel ? getLabel(move) : "Choose";
      const label = promo || fallback;
      const meta = promo ? fallback : "";
      row.innerHTML = `<div><div class="label">${esc(label)}</div><div class="meta">${esc(meta)}</div></div>`;

      const btn = document.createElement("button");
      btn.className = "btn btn-primary";
      btn.textContent = "Select";
      btn.addEventListener("click", () => {
        if (this._onPick) this._onPick(move);
        this.hide();
      });
      row.appendChild(btn);
      this.optionsEl.appendChild(row);
    }

    this.promptEl.textContent = "Choose move variant";
    this.modal.hidden = false;
  }

  hide() {
    this.modal.hidden = true;
    this.optionsEl.innerHTML = "";
    this._onPick = null;
    this._onCancel = null;
  }
}
