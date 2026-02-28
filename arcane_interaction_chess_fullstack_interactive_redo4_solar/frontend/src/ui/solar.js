function esc(s) {
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

// Canonical ids
const ITEM_SOLAR = 7;
const ABIL_REDO = 4;
const ABIL_NECRO = 8;

function hasItem(cfg, itemId) {
  if (!cfg || !cfg.items) return false;
  return cfg.items.map(Number).includes(Number(itemId));
}

function pieceHasAbility(cfg, piece, abilityId) {
  if (!cfg || !cfg.abilities) return false;
  const pt = piece.type;
  for (const s of cfg.abilities) {
    if (Number(s.ability) !== Number(abilityId)) continue;
    if (s.piece_type == null || String(s.piece_type) === pt) return true;
  }
  return false;
}

export class SolarModal {
  constructor(doc) {
    this.doc = doc;
    this.root = doc.querySelector('#solarModal');
    this.promptEl = doc.querySelector('#solarPrompt');
    this.ctxEl = doc.querySelector('#solarContext');
    this.optsEl = doc.querySelector('#solarOptions');
    this.btnClose = doc.querySelector('#btnSolarClose');

    this._onPick = null;

    this.btnClose.addEventListener('click', () => this.hide());
  }

  show(snapshot, { onPick, onClose } = {}) {
    this._onPick = onPick || null;
    this._onClose = onClose || null;

    const stm = snapshot.side_to_move;
    const cfgBySide = snapshot.player_config;
    const pc = cfgBySide ? cfgBySide[stm] : null;
    const as = snapshot.arcane_state || null;

    if (!pc || !as) {
      this.promptEl.textContent = 'Solar Necklace unavailable';
      this.ctxEl.textContent = 'No arcane state.';
      this.optsEl.innerHTML = '';
      this.root.hidden = false;
      return;
    }

    const usesLeft = as.solar_uses ? Number(as.solar_uses[stm]) : 0;
    const usesMax = as.solar_max != null ? Number(as.solar_max) : 3;

    this.promptEl.textContent = `Top up (uses left: ${usesLeft}/${usesMax})`;

    const canSolar = hasItem(pc, ITEM_SOLAR) && usesLeft > 0;

    const lines = [];
    lines.push(`Side to move: ${stm}`);
    lines.push(`Has Solar Necklace: ${hasItem(pc, ITEM_SOLAR) ? 'yes' : 'no'}`);
    lines.push(`Uses remaining: ${usesLeft}/${usesMax}`);
    this.ctxEl.textContent = lines.join('\n');

    this.optsEl.innerHTML = '';

    if (!hasItem(pc, ITEM_SOLAR)) {
      this.optsEl.innerHTML = `<div class="tiny muted">Solar Necklace not equipped for ${esc(stm)}.</div>`;
      this.root.hidden = false;
      return;
    }

    if (usesLeft <= 0) {
      this.optsEl.innerHTML = `<div class="tiny muted">No Solar uses remaining.</div>`;
      this.root.hidden = false;
      return;
    }

    // Necromancer option
    const necroMax = as.necro_max ? Number(as.necro_max[stm]) : 0;
    const necroPool = as.necro_pool ? Number(as.necro_pool[stm]) : 0;
    const hasNecro = (pc.abilities || []).some(a => Number(a.ability) === ABIL_NECRO);

    if (hasNecro && necroMax > 0) {
      const btn = document.createElement('button');
      btn.className = 'btn btn-primary';
      btn.style.width = '100%';
      btn.style.marginBottom = '8px';
      btn.disabled = !canSolar || (necroPool >= necroMax);
      btn.textContent = `Top up Necromancer pool (+1)  [${necroPool}/${necroMax}]`;
      btn.addEventListener('click', async () => {
        if (!this._onPick) return;
        await this._onPick({ kind: 'necro' });
      });
      this.optsEl.appendChild(btn);
    }

    // Redo piece options
    const redoPieces = [];
    for (const p of snapshot.pieces || []) {
      if (p.color !== stm) continue;
      if (!pieceHasAbility(pc, p, ABIL_REDO)) continue;
      const uid = Number(p.uid);
      const cur = as.redo_charges ? Number(as.redo_charges[uid] ?? 0) : 0;
      const mx = as.redo_max ? Number(as.redo_max[uid] ?? 0) : 0;
      if (mx <= 0) continue;
      if (cur >= mx) continue;
      redoPieces.push({ uid, type: p.type, pos_alg: p.pos_alg, cur, mx });
    }

    if (redoPieces.length) {
      const title = document.createElement('div');
      title.className = 'tiny muted';
      title.style.margin = '10px 0 6px';
      title.textContent = 'Top up Redo charge (+1)';
      this.optsEl.appendChild(title);

      for (const rp of redoPieces) {
        const btn = document.createElement('button');
        btn.className = 'btn';
        btn.style.width = '100%';
        btn.style.marginBottom = '6px';
        btn.disabled = !canSolar;
        btn.textContent = `${rp.type} @ ${rp.pos_alg} (uid ${rp.uid})  [${rp.cur}/${rp.mx}]`;
        btn.addEventListener('click', async () => {
          if (!this._onPick) return;
          await this._onPick({ kind: 'redo', uid: rp.uid });
        });
        this.optsEl.appendChild(btn);
      }
    }

    if (!redoPieces.length && !(hasNecro && necroMax > 0)) {
      this.optsEl.innerHTML = `<div class="tiny muted">Nothing to top up right now.</div>`;
    }

    this.root.hidden = false;
  }

  hide() {
    this.root.hidden = true;
    if (this._onClose) this._onClose();
  }
}
