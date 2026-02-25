function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }

function hexToRgb(hex) {
  const h = hex.replace("#", "");
  const n = parseInt(h.length === 3 ? h.split("").map(c => c + c).join("") : h, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function rgbToHex(r, g, b) {
  const to = (x) => x.toString(16).padStart(2, "0");
  return `#${to(r)}${to(g)}${to(b)}`;
}

function shade(hex, t) {
  // cell-shade: t in [-1..1]
  const [r, g, b] = hexToRgb(hex);
  const k = t;
  const rr = clamp(Math.round(r + (k * 70)), 0, 255);
  const gg = clamp(Math.round(g + (k * 70)), 0, 255);
  const bb = clamp(Math.round(b + (k * 70)), 0, 255);
  return rgbToHex(rr, gg, bb);
}

function quantize(x) {
  // snap to 3 bands
  if (x < -0.25) return -0.55;
  if (x < 0.25) return 0;
  return 0.55;
}

const BASE = {
  WHITE: "#e8eef6",
  BLACK: "#1a2431",
};

const ACCENT = {
  WHITE: "#7dd3fc",
  BLACK: "#a78bfa",
};

export function pieceKey(type, color, quality, tileW) {
  return `${type}_${color}_${quality}_${Math.round(tileW)}`;
}

export function buildPieceSprite({ type, color, quality, tileW, tileH }) {
  // sprite size (screen space)
  const w = Math.ceil(tileW * 1.10);
  const h = Math.ceil(tileH * 2.05);
  const cnv = document.createElement("canvas");
  cnv.width = w;
  cnv.height = h;
  const ctx = cnv.getContext("2d");

  const base = BASE[color];
  const outline = "#070b10";
  const accent = ACCENT[color];

  // type parameters: height and cap
  const t = {
    Pawn: { hh: 0.70, cap: 0.34 },
    Knight: { hh: 0.92, cap: 0.40 },
    Bishop: { hh: 0.98, cap: 0.38 },
    Rook: { hh: 0.98, cap: 0.44 },
    Queen: { hh: 1.10, cap: 0.46 },
    King: { hh: 1.15, cap: 0.46 },
  }[type] || { hh: 0.90, cap: 0.40 };

  const cx = w * 0.5;
  const groundY = h * 0.76;
  const height = tileH * (1.2 + t.hh);

  // helper: draw iso-ish prism (top + two sides)
  function drawPrism(x, y, topW, topH, heightPx, fillTop, fillL, fillR) {
    const hw = topW * 0.5;
    const hh = topH * 0.5;

    // top (diamond)
    const top = [
      [x, y - hh],
      [x + hw, y],
      [x, y + hh],
      [x - hw, y],
    ];

    // extrude down
    const dy = heightPx;
    const btm = top.map(([px, py]) => [px, py + dy]);

    // right face: top[1]->top[2]->btm[2]->btm[1]
    const right = [top[1], top[2], btm[2], btm[1]];
    const left = [top[3], top[2], btm[2], btm[3]];

    ctx.lineJoin = "round";

    // faces back-to-front: left, right, top
    ctx.beginPath();
    poly(ctx, left);
    ctx.fillStyle = fillL;
    ctx.fill();

    ctx.beginPath();
    poly(ctx, right);
    ctx.fillStyle = fillR;
    ctx.fill();

    ctx.beginPath();
    poly(ctx, top);
    ctx.fillStyle = fillTop;
    ctx.fill();

    // outline
    if (quality > 0) {
      ctx.strokeStyle = outline;
      ctx.lineWidth = Math.max(1, tileW * 0.012);
      ctx.beginPath();
      poly(ctx, left);
      poly(ctx, right);
      poly(ctx, top);
      ctx.stroke();
    }
  }

  function poly(c, pts) {
    c.moveTo(pts[0][0], pts[0][1]);
    for (let i = 1; i < pts.length; i++) c.lineTo(pts[i][0], pts[i][1]);
    c.closePath();
  }

  // simple light model (cel-shaded)
  const topShade = quantize(0.55);
  const leftShade = quantize(-0.15);
  const rightShade = quantize(0.15);

  // base pedestal
  drawPrism(
    cx, groundY,
    tileW * 0.50, tileH * 0.36,
    tileH * 0.22,
    shade(base, topShade),
    shade(base, leftShade),
    shade(base, rightShade)
  );

  // body
  const bodyTopW = tileW * (0.36 + t.cap * 0.20);
  const bodyTopH = tileH * (0.26 + t.cap * 0.10);
  const bodyHeight = height * 0.55;
  drawPrism(
    cx, groundY - tileH * 0.16,
    bodyTopW, bodyTopH,
    bodyHeight,
    shade(base, quantize(0.45)),
    shade(base, quantize(-0.25)),
    shade(base, quantize(0.05))
  );

  // cap
  drawPrism(
    cx, groundY - tileH * 0.16,
    tileW * (0.24 + t.cap * 0.25), tileH * (0.18 + t.cap * 0.20),
    tileH * (0.10 + t.cap * 0.08),
    shade(base, quantize(0.65)),
    shade(base, quantize(-0.10)),
    shade(base, quantize(0.20))
  );

  // crown (queen/king) accents
  if (type === "King" || type === "Queen") {
    const y = groundY - tileH * 0.27;
    ctx.fillStyle = shade(accent, 0.25);
    ctx.strokeStyle = outline;
    ctx.lineWidth = Math.max(1, tileW * 0.010);
    ctx.beginPath();
    ctx.arc(cx, y - tileH * 0.15, tileW * 0.07, 0, Math.PI * 2);
    ctx.fill();
    if (quality > 0) ctx.stroke();

    if (type === "King") {
      // small cross
      ctx.strokeStyle = shade(accent, 0.55);
      ctx.lineWidth = Math.max(2, tileW * 0.010);
      ctx.beginPath();
      ctx.moveTo(cx, y - tileH * 0.32);
      ctx.lineTo(cx, y - tileH * 0.18);
      ctx.moveTo(cx - tileW * 0.04, y - tileH * 0.25);
      ctx.lineTo(cx + tileW * 0.04, y - tileH * 0.25);
      ctx.stroke();
    }
  }

  // letter mark (minimalist, no sprites)
  if (quality > 1) {
    const map = { Pawn: "P", Knight: "N", Bishop: "B", Rook: "R", Queen: "Q", King: "K" };
    const ch = map[type] || "?";
    ctx.font = `700 ${Math.round(tileH * 0.42)}px ui-sans-serif, system-ui`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillStyle = color === "WHITE" ? "rgba(10,14,20,.75)" : "rgba(255,255,255,.85)";
    ctx.fillText(ch, cx, groundY + tileH * 0.16);
  }

  // soft shadow
  if (quality > 0) {
    ctx.globalCompositeOperation = "destination-over";
    ctx.fillStyle = "rgba(0,0,0,.35)";
    ctx.beginPath();
    ctx.ellipse(cx, groundY + tileH * 0.30, tileW * 0.16, tileH * 0.10, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.globalCompositeOperation = "source-over";
  }

  // anchor: bottom center
  return { canvas: cnv, ax: cx, ay: groundY + tileH * 0.32 };
}
