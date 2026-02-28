const PIECE_TYPES = ["Pawn","Knight","Bishop","Rook","Queen","King"];

function el(tag, cls = null, txt = null) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (txt != null) n.textContent = txt;
  return n;
}

export class LoadoutModal {
  constructor(modalEl, defs) {
    this.modalEl = modalEl;
    this.defs = defs;

    this._grids = {
      WHITE: modalEl.querySelector('#loadoutWhite .loadoutGrid'),
      BLACK: modalEl.querySelector('#loadoutBlack .loadoutGrid'),
    };

    this.state = {
      WHITE: { element_id: 2, items: new Set(), abilities: new Map() },
      BLACK: { element_id: 2, items: new Set(), abilities: new Map() },
    };

    this._renderSide("WHITE");
    this._renderSide("BLACK");
  }

  show() { this.modalEl.hidden = false; }
  hide() { this.modalEl.hidden = true; }

  _renderSide(color) {
    const grid = this._grids[color];
    grid.innerHTML = "";

    // Element
    const gEl = el("div", "group");
    gEl.appendChild(el("div", "groupTitle", "Element"));
    const sel = el("select", "select");
    for (const e of this.defs.elements) {
      const opt = el("option");
      opt.value = String(e.id);
      opt.textContent = e.name;
      if (e.id === this.state[color].element_id) opt.selected = true;
      sel.appendChild(opt);
    }
    sel.addEventListener("change", () => {
      this.state[color].element_id = Number(sel.value);
      this._updateAbilityControls(color);
      this._updateBudgets(color);
    });
    gEl.appendChild(sel);
    this._elementControl = this._elementControl || {};
    this._elementControl[color] = { sel, reason: el("div", "tiny muted", "") };
    gEl.appendChild(this._elementControl[color].reason);

    // Items
    const gItems = el("div", "group");
    gItems.appendChild(el("div", "groupTitle", "Items (≤ 4 cost)"));
    for (const it of this.defs.items) {
      const row = el("label");
      const cb = el("input");
      cb.type = "checkbox";
      cb.checked = this.state[color].items.has(it.id);
      cb.addEventListener("change", () => {
        if (cb.checked) this.state[color].items.add(it.id);
        else this.state[color].items.delete(it.id);
        this._applyItemConflicts(color, it.id, cb.checked);
        this._updateAbilityControls(color);
        this._updateBudgets(color);
      });
      row.appendChild(cb);
      row.appendChild(el("span", null, `${it.name} (cost ${it.slot_cost})`));
      const reason = el("div", "tiny muted", "");
      row.appendChild(reason);
      gItems.appendChild(row);

      this._itemControls = this._itemControls || { WHITE: new Map(), BLACK: new Map() };
      this._itemControls[color].set(it.id, { cb, reason });
    }
    this._itemsBudgetEl = this._itemsBudgetEl || {};
    this._itemsBudgetEl[color] = el("div", "tiny muted", "");
    gItems.appendChild(this._itemsBudgetEl[color]);

    // Abilities
    const gAbil = el("div", "group");
    gAbil.appendChild(el("div", "groupTitle", "Army Abilities"));

    this._abilControls = this._abilControls || { WHITE: [], BLACK: [] };
    this._abilControls[color] = [];

    for (const ab of this.defs.abilities) {
      const row = el("div");
      row.style.display = "grid";
      row.style.gridTemplateColumns = "18px 1fr 120px";
      row.style.gap = "8px";
      row.style.alignItems = "center";
      row.style.margin = "6px 0";

      const cb = el("input");
      cb.type = "checkbox";
      cb.checked = this.state[color].abilities.has(ab.id);

      const label = el("div", null, `${ab.name}${ab.consumable ? " (consumable)" : ""}`);
      label.className = "tiny";

      const psel = el("select", "select");
      psel.innerHTML = `<option value="">Army-wide</option>` + PIECE_TYPES.map(t => `<option value="${t}">${t}</option>`).join("");

      const cur = this.state[color].abilities.get(ab.id);
      if (cur && cur.piece_type) psel.value = cur.piece_type;

      cb.addEventListener("change", () => {
        if (cb.checked) {
          this.state[color].abilities.set(ab.id, { ability: ab.id, piece_type: psel.value || null });
        } else {
          this.state[color].abilities.delete(ab.id);
        }
        this._updateBudgets(color);
      });

      psel.addEventListener("change", () => {
        if (this.state[color].abilities.has(ab.id)) {
          this.state[color].abilities.set(ab.id, { ability: ab.id, piece_type: psel.value || null });
        }
      });

      row.appendChild(cb);
      row.appendChild(label);
      row.appendChild(psel);

      gAbil.appendChild(row);
      this._abilControls[color].push({ ab, cb, psel });
    }

    this._abilBudgetEl = this._abilBudgetEl || {};
    this._abilBudgetEl[color] = el("div", "tiny muted", "");
    gAbil.appendChild(this._abilBudgetEl[color]);

    grid.appendChild(gEl);
    grid.appendChild(gItems);
    grid.appendChild(gAbil);

    this._updateAbilityControls(color);
    this._updateBudgets(color);
  }

  _hasItem(color, itemId) {
    return this.state[color].items.has(itemId);
  }

  _abilitySlots(color) {
    // baseline 1 + gloves/ring
    let slots = 1;
    if (this._hasItem(color, 3)) slots += 1; // Dual
    if (this._hasItem(color, 4)) slots += 2; // Triple
    if (this._hasItem(color, 5)) slots += 3; // Ring
    return slots;
  }

  _itemCost(color) {
    const byId = new Map(this.defs.items.map(i => [i.id, i.slot_cost]));
    let c = 0;
    for (const it of this.state[color].items) c += Number(byId.get(it) || 0);
    return c;
  }

  _updateBudgets(color) {
    const ic = this._itemCost(color);
    const slots = this._abilitySlots(color);
    const used = this.state[color].abilities.size;

    this._itemsBudgetEl[color].textContent = `Cost used: ${ic}/4`;
    this._itemsBudgetEl[color].style.color = (ic > 4) ? "#fb7185" : "#a4b3c7";

    this._abilBudgetEl[color].textContent = `Ability slots: ${used}/${slots}`;
    this._abilBudgetEl[color].style.color = (used > slots) ? "#fb7185" : "#a4b3c7";

    // soft disable if exceeded
    for (const c of this._abilControls[color]) {
      if (!c.cb.checked && used >= slots) c.cb.disabled = true;
      else c.cb.disabled = false;
    }
  }

  _updateAbilityControls(color) {
    const allowPieceType = this._isLightningSelected(color) || this._hasItem(color, 1); // Lightning or Multitasker

    for (const c of this._abilControls[color]) {
      c.psel.disabled = !allowPieceType;
      if (!allowPieceType) {
        c.psel.value = "";
        if (this.state[color].abilities.has(c.ab.id)) {
          this.state[color].abilities.set(c.ab.id, { ability: c.ab.id, piece_type: null });
        }
      }
    }

    this._syncConflictControls(color);
  }

  _setItemChecked(color, itemId, checked) {
    if (checked) this.state[color].items.add(itemId);
    else this.state[color].items.delete(itemId);
    const ctl = this._itemControls?.[color]?.get(itemId);
    if (ctl) ctl.cb.checked = checked;
  }

  _applyItemConflicts(color, itemId, checked) {
    if (!checked) return;
    if (itemId === 4) {
      this._setItemChecked(color, 3, false);
      this._setItemChecked(color, 5, false);
      return;
    }
    if (itemId === 3) {
      this._setItemChecked(color, 4, false);
      this._setItemChecked(color, 5, false);
      return;
    }
    if (itemId === 5) {
      this._setItemChecked(color, 3, false);
      this._setItemChecked(color, 4, false);
      return;
    }
    if (itemId === 1 && this._isLightningSelected(color)) {
      this._setItemChecked(color, 1, false);
    }
  }

  _isLightningSelected(color) {
    const elId = this.state[color].element_id;
    const e = this.defs.elements.find((x) => x.id === elId);
    return Boolean(e && String(e.name).toLowerCase().includes("lightning"));
  }

  _syncConflictControls(color) {
    const dual = this._hasItem(color, 3);
    const triple = this._hasItem(color, 4);
    const ring = this._hasItem(color, 5);
    const lightning = this._isLightningSelected(color);

    if (lightning && this._hasItem(color, 1)) {
      this._setItemChecked(color, 1, false);
    }

    const setItemState = (itemId, disabled, reason) => {
      const ctl = this._itemControls?.[color]?.get(itemId);
      if (!ctl) return;
      ctl.cb.disabled = disabled;
      ctl.reason.textContent = reason;
      ctl.reason.style.display = reason ? "block" : "none";
    };

    setItemState(3, false, "");
    setItemState(4, false, "");
    setItemState(5, false, "");
    setItemState(1, false, "");

    if (triple) {
      setItemState(3, true, "Disabled: conflicts with Triple Adept’s Gloves.");
      setItemState(5, true, "Disabled: conflicts with Triple Adept’s Gloves.");
    }
    if (dual) {
      setItemState(4, true, "Disabled: conflicts with Dual Adept’s Gloves.");
      setItemState(5, true, "Disabled: conflicts with Dual Adept’s Gloves.");
    }
    if (ring) {
      setItemState(3, true, "Disabled: conflicts with Headmaster Ring.");
      setItemState(4, true, "Disabled: conflicts with Headmaster Ring.");
    }

    const elCtl = this._elementControl?.[color];
    if (!elCtl) return;
    const lightningOpt = Array.from(elCtl.sel.options).find((opt) => String(opt.textContent).toLowerCase().includes("lightning"));
    if (lightningOpt) lightningOpt.disabled = this._hasItem(color, 1);

    const multitaskerReason = lightning
      ? "Disabled: conflicts with Lightning element."
      : "";
    if (multitaskerReason) {
      setItemState(1, true, multitaskerReason);
    }

    const elReason = this._hasItem(color, 1)
      ? "Lightning element is disabled while Multitasker’s Schedule is equipped."
      : "";
    elCtl.reason.textContent = elReason;
    elCtl.reason.style.display = elReason ? "block" : "none";
  }

  getConfigs() {
    const cfg = {};
    for (const color of ["WHITE","BLACK"]) {
      cfg[color] = {
        element_id: this.state[color].element_id,
        items: Array.from(this.state[color].items),
        abilities: Array.from(this.state[color].abilities.values()),
      };
    }
    return cfg;
  }
}
