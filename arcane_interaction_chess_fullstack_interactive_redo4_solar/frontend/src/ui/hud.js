function esc(s) {
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

export function findKingSq(snapshot, color) {
  if (!snapshot) return null;
  const c = String(color || "WHITE");
  for (const p of snapshot.pieces) {
    if (p.type === "King" && p.color === c) return Number(p.pos);
  }
  return null;
}

export class HUD {
  constructor(root) {
    this.root = root;
    this.turnEl = root.querySelector("#turn");
    this.checkEl = root.querySelector("#check");
    this.fenEl = root.querySelector("#fen");
    this.arcaneEl = root.querySelector("#arcane");
    this.effectsEl = root.querySelector("#effects");
    this.movesEl = root.querySelector("#moves");
    this.toastEl = root.querySelector("#toast");
    this.fpsEl = root.querySelector("#fps");
  }

  toast(msg, ms = 1600) {
    if (!this.toastEl) return;
    this.toastEl.hidden = false;
    this.toastEl.textContent = msg;
    clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => { this.toastEl.hidden = true; }, ms);
  }

  setFPS(fps) {
    if (this.fpsEl) this.fpsEl.textContent = String(fps.toFixed(0));
  }

  render(snapshot, gameState) {
    if (!snapshot) return;
    const stm = snapshot.side_to_move;
    this.turnEl.textContent = `${stm} • ply ${snapshot.ply}`;

    const inCheck = !!snapshot.check;
    this.checkEl.textContent = snapshot.checkmate ? "CHECKMATE" : (inCheck ? "CHECK" : "—");
    this.checkEl.style.color = snapshot.checkmate ? "#fb7185" : (inCheck ? "#fb7185" : "#a4b3c7");

    this.fenEl.textContent = snapshot.fen || "—";

    // arcane resources
    const as = snapshot.arcane_state;
    const cfgBySide = snapshot.player_config;
    const lines = [];
    if (cfgBySide) {
      for (const side of ["WHITE","BLACK"]) {
        const cfg = cfgBySide[side];
        const el = cfg ? cfg.element : "?";
        const items = (cfg && cfg.items) ? cfg.items.join(",") : "";
        const abil = (cfg && cfg.abilities) ? cfg.abilities.map(a => a.piece_type ? `${a.ability}:${a.piece_type}` : String(a.ability)).join(",") : "";
        lines.push(`${side}: el=${el} items=[${items}] abil=[${abil}]`);
      }
    }
    if (as) {
      lines.push(`necro_pool W:${as.necro_pool.WHITE}/${as.necro_max.WHITE} B:${as.necro_pool.BLACK}/${as.necro_max.BLACK}`);
      lines.push(`solar_uses W:${as.solar_uses.WHITE}/${as.solar_max} B:${as.solar_uses.BLACK}/${as.solar_max}`);
    }
    this.arcaneEl.textContent = lines.join("\n");

    this._renderEffects(gameState.effects || []);
    this._renderMoves(gameState.moveHistory || []);
  }

  _renderEffects(effects) {
    const el = this.effectsEl;
    if (!el) return;
    el.innerHTML = "";
    if (!effects.length) {
      el.innerHTML = `<div class="tiny muted">No effects.</div>`;
      return;
    }

    for (const e of effects.slice(-20).reverse()) {
      const t = e.type || "effect";
      const tagClass = (t === "double_kill" || t === "quantum_kill" || t === "necromancer") ? "off" : (t === "block_path" || t === "redo") ? "def" : (t === "poisoned_dagger") ? "warn" : "item";
      const div = document.createElement("div");
      div.className = "e";
      div.innerHTML = `<span class="tag ${tagClass}">${esc(t)}</span><span class="mono tiny">${esc(JSON.stringify(e))}</span>`;
      el.appendChild(div);
    }
  }

  _renderMoves(hist) {
    const el = this.movesEl;
    if (!el) return;
    el.innerHTML = "";
    if (!hist.length) {
      el.innerHTML = `<div class="tiny muted">No moves yet.</div>`;
      return;
    }

    // group by fullmove-ish pairs
    let idx = 1;
    for (let i = 0; i < hist.length; i += 2) {
      const row = document.createElement("div");
      row.className = "row";
      const w = hist[i];
      const b = hist[i + 1];
      row.innerHTML = `<div class="ply">${idx}.</div><div class="san">${esc(w.san)}</div><div class="san muted">${b ? esc(b.san) : ""}</div>`;
      el.appendChild(row);
      idx++;
    }
  }
}
