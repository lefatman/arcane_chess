// Isometric projection helpers

export function makeIso(tileW, tileH, originX, originY) {
  const halfW = tileW * 0.5;
  const halfH = tileH * 0.5;

  function sqToScreen(file, rank) {
    const x = originX + (file - rank) * halfW;
    const y = originY + (file + rank) * halfH;
    return [x, y];
  }

  function screenToFR(x, y) {
    const u = (x - originX) / halfW;
    const v = (y - originY) / halfH;
    const f = (u + v) * 0.5;
    const r = (v - u) * 0.5;
    return [f, r];
  }

  return { tileW, tileH, originX, originY, sqToScreen, screenToFR };
}

export function tilePoly(iso, file, rank) {
  const [cx, cy] = iso.sqToScreen(file, rank);
  const hw = iso.tileW * 0.5;
  const hh = iso.tileH * 0.5;
  // rhombus vertices (top, right, bottom, left)
  return [
    [cx, cy - hh],
    [cx + hw, cy],
    [cx, cy + hh],
    [cx - hw, cy],
  ];
}

export function pointInPoly(px, py, poly) {
  // convex quad; use winding
  let inside = true;
  for (let i = 0; i < poly.length; i++) {
    const [x1, y1] = poly[i];
    const [x2, y2] = poly[(i + 1) % poly.length];
    const cross = (x2 - x1) * (py - y1) - (y2 - y1) * (px - x1);
    if (cross < 0) { inside = false; break; }
  }
  if (inside) return true;
  // try opposite winding
  inside = true;
  for (let i = 0; i < poly.length; i++) {
    const [x1, y1] = poly[i];
    const [x2, y2] = poly[(i + 1) % poly.length];
    const cross = (x2 - x1) * (py - y1) - (y2 - y1) * (px - x1);
    if (cross > 0) { inside = false; break; }
  }
  return inside;
}

export function pickSquare(iso, px, py) {
  // estimate then refine by testing neighboring tiles
  const [f0, r0] = iso.screenToFR(px, py);
  const cf = Math.floor(f0);
  const cr = Math.floor(r0);

  for (let dr = -1; dr <= 1; dr++) {
    for (let df = -1; df <= 1; df++) {
      const f = cf + df;
      const r = cr + dr;
      if (f < 0 || f > 7 || r < 0 || r > 7) continue;
      const poly = tilePoly(iso, f, r);
      if (pointInPoly(px, py, poly)) return [f, r];
    }
  }
  // fallback nearest
  const f = Math.round(f0);
  const r = Math.round(r0);
  if (f < 0 || f > 7 || r < 0 || r > 7) return null;
  return [f, r];
}
