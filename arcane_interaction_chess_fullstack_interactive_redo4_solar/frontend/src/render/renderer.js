import { makeIso, tilePoly, pickSquare } from "./iso.js";
import { Animator, Tween, easeInOutQuad } from "./anim.js";
import { buildPieceSprite, pieceKey } from "./pieces.js";

function sqToFR(sq) {
  const file = sq & 7;
  const rank = (sq >> 3) & 7;
  return [file, rank];
}

function frToSq(file, rank) {
  return (rank * 8) + file;
}

function viewRank(rank) { return 7 - rank; }
function unviewRank(vr) { return 7 - vr; }

function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }

function lerp(a, b, t) { return a + (b - a) * t; }

export class Renderer {
  constructor(canvas, { quality = 1 } = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d", { alpha: false, desynchronized: true });

    this.quality = quality;
    this.anim = new Animator();

    this.iso = null;
    this.tiles = new Array(64);
    this.tileOrder = [];

    this.sprites = new Map(); // key -> {canvas, ax, ay}
    this.visual = new Map(); // uid -> {uid, type, color, sq, x,y, alpha, scale}

    this.selectedSq = null;
    this.legalByFrom = new Map(); // fromSq -> [move]
    this.destSet = new Set();

    this._pulse = 0;

    this.resize(canvas.clientWidth || canvas.width, canvas.clientHeight || canvas.height);
  }

  setQuality(q) {
    this.quality = q;
    this.sprites.clear();
  }

  resize(w, h) {
    const dpr = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
    this.canvas.width = Math.floor(w * dpr);
    this.canvas.height = Math.floor(h * dpr);
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    // choose tile size based on pane
    const tileW = clamp(Math.floor(Math.min(w, h) / 6.2), 58, 112);
    const tileH = Math.floor(tileW * 0.50);

    // origin so that board is centered
    const boardW = tileW * 8;
    const boardH = tileH * 8;
    const originX = w * 0.5;
    const originY = (h * 0.16);

    this.iso = makeIso(tileW, tileH, originX, originY);

    // precompute tile polygons and draw order
    this.tileOrder = [];
    for (let r = 0; r < 8; r++) {
      for (let f = 0; f < 8; f++) {
        const sq = frToSq(f, r);
        const vr = viewRank(r);
        this.tiles[sq] = { sq, f, r, vr, poly: tilePoly(this.iso, f, vr) };
        this.tileOrder.push({ sq, z: f + vr });
      }
    }
    this.tileOrder.sort((a, b) => a.z - b.z);

    // re-render sprites at new tile size
    this.sprites.clear();
  }

  setLegalMoves(moves) {
    this.legalByFrom.clear();
    for (const m of (moves || [])) {
      const fr = Number(m.from);
      if (!this.legalByFrom.has(fr)) this.legalByFrom.set(fr, []);
      this.legalByFrom.get(fr).push(m);
    }
    this._rebuildDestSet();
  }

  _rebuildDestSet() {
    this.destSet.clear();
    if (this.selectedSq == null) return;
    const arr = this.legalByFrom.get(this.selectedSq) || [];
    for (const m of arr) this.destSet.add(Number(m.to));
  }

  setSelectionSquare(sq) {
    this.selectedSq = sq;
    this._rebuildDestSet();
  }

  clearSelection() {
    this.selectedSq = null;
    this._rebuildDestSet();
  }

  squareAtScreen(x, y) {
    const iso = this.iso;
    if (!iso) return null;
    const picked = pickSquare(iso, x, y);
    if (!picked) return null;
    const [f, vr] = picked;
    const r = unviewRank(vr);
    return frToSq(f, r);
  }

  _spriteFor(type, color) {
    const iso = this.iso;
    const key = pieceKey(type, color, this.quality, iso.tileW);
    let sp = this.sprites.get(key);
    if (!sp) {
      sp = buildPieceSprite({ type, color, quality: this.quality, tileW: iso.tileW, tileH: iso.tileH });
      this.sprites.set(key, sp);
    }
    return sp;
  }

  syncSnapshot(snapshot) {
    this.visual.clear();
    if (!snapshot) return;
    for (const p of snapshot.pieces) {
      const uid = Number(p.uid);
      this.visual.set(uid, {
        uid,
        type: p.type,
        color: p.color,
        sq: Number(p.pos),
        alpha: 1,
        scale: 1,
        meta: p.meta || {},
      });
    }
    this._positionAll();
  }

  _positionAll() {
    for (const vp of this.visual.values()) {
      const { x, y } = this._screenPosForSq(vp.sq);
      vp.x = x;
      vp.y = y;
    }
  }

  _screenPosForSq(sq) {
    const [f, r] = sqToFR(sq);
    const vr = viewRank(r);
    const [x, y] = this.iso.sqToScreen(f, vr);
    return { x, y };
  }

  applyResult(result) {
    // animate from current visuals to result.after via diff
    const diff = result.diff;

    // moved
    for (const m of (diff.moved || [])) {
      const uid = Number(m.uid);
      const vp = this.visual.get(uid);
      if (!vp) continue;
      const fromSq = Number(m.from);
      const toSq = Number(m.to);
      const fromPos = this._screenPosForSq(fromSq);
      const toPos = this._screenPosForSq(toSq);
      vp.sq = fromSq;
      vp.x = fromPos.x;
      vp.y = fromPos.y;

      const dur = 220;
      this.anim.add(new Tween({
        duration: dur,
        ease: easeInOutQuad,
        onUpdate: (t) => {
          vp.x = lerp(fromPos.x, toPos.x, t);
          vp.y = lerp(fromPos.y, toPos.y, t);
          vp.scale = 1 + (Math.sin(t * Math.PI) * 0.05);
        },
        onDone: () => {
          vp.sq = toSq;
          vp.x = toPos.x;
          vp.y = toPos.y;
          vp.scale = 1;
        }
      }));
    }

    // removed
    for (const r of (diff.removed || [])) {
      const uid = Number(r.uid);
      const vp = this.visual.get(uid);
      if (!vp) continue;
      this.anim.add(new Tween({
        duration: 180,
        onUpdate: (t) => {
          vp.alpha = 1 - t;
          vp.scale = 1 - t * 0.25;
        },
        onDone: () => {
          this.visual.delete(uid);
        }
      }));
    }

    // added
    for (const a of (diff.added || [])) {
      const uid = Number(a.uid);
      const sq = Number(a.pos);
      const pos = this._screenPosForSq(sq);
      const vp = {
        uid,
        type: a.type,
        color: a.color,
        sq,
        x: pos.x,
        y: pos.y,
        alpha: 0,
        scale: 0.85,
        meta: a.meta || {},
      };
      this.visual.set(uid, vp);
      this.anim.add(new Tween({
        duration: 220,
        onUpdate: (t) => {
          vp.alpha = t;
          vp.scale = 0.85 + t * 0.15;
        },
        onDone: () => {
          vp.alpha = 1;
          vp.scale = 1;
        }
      }));
    }

    // meta changes
    for (const mc of (diff.meta_changed || [])) {
      const uid = Number(mc.uid);
      const vp = this.visual.get(uid);
      if (vp) vp.meta = mc.after || {};
    }

    // selection: if selected piece was removed, clear
    if (this.selectedSq != null) {
      const stillHas = Array.from(this.visual.values()).some(v => v.sq === this.selectedSq);
      if (!stillHas) this.clearSelection();
    }
  }

  step(dt) {
    this._pulse += dt;
    this.anim.step(dt);
  }

  draw(snapshot, { highlightSquares = [], checkSq = null } = {}) {
    const ctx = this.ctx;
    const iso = this.iso;
    if (!iso) return;

    const hl = new Set(highlightSquares || []);

    const w = this.canvas.clientWidth;
    const h = this.canvas.clientHeight;

    // background
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#0b0f14";
    ctx.fillRect(0, 0, w, h);

    // board tiles
    for (const o of this.tileOrder) {
      const tile = this.tiles[o.sq];
      const light = ((tile.f + tile.r) & 1) === 0;
      const base = light ? "#182233" : "#121b28";
      const top = light ? "#1d2a3d" : "#162133";
      const edge = light ? "rgba(0,0,0,.42)" : "rgba(0,0,0,.52)";

      // top face
      ctx.beginPath();
      ctx.moveTo(tile.poly[0][0], tile.poly[0][1]);
      for (let i = 1; i < 4; i++) ctx.lineTo(tile.poly[i][0], tile.poly[i][1]);
      ctx.closePath();
      ctx.fillStyle = top;
      ctx.fill();

      // subtle inner shading
      if (this.quality > 0) {
        ctx.strokeStyle = edge;
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      // highlight destination squares
      if (this.destSet.has(tile.sq)) {
        ctx.strokeStyle = "rgba(125,211,252,.85)";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(tile.poly[0][0], tile.poly[0][1]);
        for (let i = 1; i < 4; i++) ctx.lineTo(tile.poly[i][0], tile.poly[i][1]);
        ctx.closePath();
        ctx.stroke();
      }

      // external highlight squares (decisions, etc.)
      if (hl.has(tile.sq)) {
        const pulse = 0.5 + 0.5 * Math.sin(this._pulse * 0.01 + tile.sq);
        ctx.strokeStyle = `rgba(251,191,36,${0.35 + pulse * 0.35})`;
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.moveTo(tile.poly[0][0], tile.poly[0][1]);
        for (let i = 1; i < 4; i++) ctx.lineTo(tile.poly[i][0], tile.poly[i][1]);
        ctx.closePath();
        ctx.stroke();
      }

      // selected square
      if (this.selectedSq === tile.sq) {
        ctx.strokeStyle = "rgba(167,139,250,.95)";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(tile.poly[0][0], tile.poly[0][1]);
        for (let i = 1; i < 4; i++) ctx.lineTo(tile.poly[i][0], tile.poly[i][1]);
        ctx.closePath();
        ctx.stroke();
      }

      // check highlight square
      if (checkSq != null && tile.sq === checkSq) {
        const pulse = 0.5 + 0.5 * Math.sin(this._pulse * 0.008);
        ctx.strokeStyle = `rgba(251,113,133,${0.45 + pulse * 0.35})`;
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.moveTo(tile.poly[0][0], tile.poly[0][1]);
        for (let i = 1; i < 4; i++) ctx.lineTo(tile.poly[i][0], tile.poly[i][1]);
        ctx.closePath();
        ctx.stroke();
      }
    }

    // pieces (sort by y so nearer pieces draw last)
    const arr = Array.from(this.visual.values());
    arr.sort((a, b) => (a.y - b.y));

    for (const p of arr) {
      const sp = this._spriteFor(p.type, p.color);
      ctx.globalAlpha = p.alpha;
      const x = p.x - sp.ax * p.scale;
      const y = p.y - sp.ay * p.scale;
      const ww = sp.canvas.width * p.scale;
      const hh = sp.canvas.height * p.scale;

      // ability aura (very cheap)
      if (this.quality > 0 && p.meta && p.meta.block_dir) {
        const pulse = 0.5 + 0.5 * Math.sin(this._pulse * 0.01 + p.uid);
        ctx.save();
        ctx.globalAlpha = 0.10 + pulse * 0.10;
        ctx.fillStyle = "#7dd3fc";
        ctx.beginPath();
        ctx.ellipse(p.x, p.y + iso.tileH * 0.10, iso.tileW * 0.18, iso.tileH * 0.12, 0, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      }

      ctx.drawImage(sp.canvas, x, y, ww, hh);
    }
    ctx.globalAlpha = 1;

    // subtle vignette
    if (this.quality > 1) {
      const grd = ctx.createRadialGradient(w * 0.5, h * 0.5, Math.min(w, h) * 0.2, w * 0.5, h * 0.5, Math.max(w, h) * 0.7);
      grd.addColorStop(0, "rgba(0,0,0,0)");
      grd.addColorStop(1, "rgba(0,0,0,.35)");
      ctx.fillStyle = grd;
      ctx.fillRect(0, 0, w, h);
    }
  }
}
