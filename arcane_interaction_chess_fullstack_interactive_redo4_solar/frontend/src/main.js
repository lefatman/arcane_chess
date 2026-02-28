import { ApiClient } from "./api.js";
import { GameState } from "./state.js";
import { Renderer } from "./render/renderer.js";
import { HUD, findKingSq } from "./ui/hud.js";
import { LoadoutModal } from "./ui/loadout.js";
import { DecisionModal } from "./ui/decisions.js";
import { SolarModal } from "./ui/solar.js";
import { PromotionPicker } from "./ui/promotion_picker.js";

const api = new ApiClient("");

const canvas = document.querySelector("#board");
const hud = new HUD(document);
const game = new GameState();

let renderer = new Renderer(canvas, { quality: 1 });

// modal
const modalEl = document.querySelector("#modal");
let loadout = null;

const btnNewGame = document.querySelector("#btnNewGame");
const btnSolar = document.querySelector("#btnSolar");
const btnUndo = document.querySelector("#btnUndo");
const btnReset = document.querySelector("#btnReset");
const btnCloseModal = document.querySelector("#btnCloseModal");
const btnStart = document.querySelector("#btnStart");
const rngSeedEl = document.querySelector("#rngSeed");
const qualitySel = document.querySelector("#quality");

const decisionModal = new DecisionModal(document);
const solarModal = new SolarModal(document);
const promotionPicker = new PromotionPicker(document);
let decisionActive = false;
let decisionHighlights = [];

function hasDisambiguatedVariants(moves) {
  if (!moves || moves.length <= 1) return false;
  let kind = null;
  let promoteTo = null;
  for (const move of moves) {
    const moveKind = move && move.kind != null ? String(move.kind) : "";
    const movePromote = move && move.promote_to != null ? String(move.promote_to) : "";
    if (moveKind === "promotion") return true;
    if (kind == null) {
      kind = moveKind;
      promoteTo = movePromote;
      continue;
    }
    if (kind !== moveKind || promoteTo !== movePromote) return true;
  }
  return false;
}

function moveChoiceLabel(move) {
  const tags = [];
  const kind = move && move.kind != null ? String(move.kind) : "";
  const promoteTo = move && move.promote_to != null ? String(move.promote_to) : "";
  if (kind) tags.push(kind.replace(/_/g, " "));
  if (promoteTo) tags.push(`promote to ${promoteTo}`);
  if (move && move.is_capture) tags.push("capture");
  if (move && move.is_check) tags.push("check");
  if (move && move.is_mate) tags.push("mate");
  if (move && move.is_en_passant) tags.push("en passant");
  if (move && move.is_castle_kingside) tags.push("castle kingside");
  if (move && move.is_castle_queenside) tags.push("castle queenside");
  if (move && move.uid != null) tags.push(`uid ${move.uid}`);
  return tags.length ? tags.join(" • ") : "standard move";
}

async function pickMoveVariant(moves) {
  if (!hasDisambiguatedVariants(moves)) return moves[0];
  return new Promise((resolve) => {
    promotionPicker.show(moves, {
      getLabel: moveChoiceLabel,
      onPick: (move) => resolve(move),
      onCancel: () => resolve(null),
    });
  });
}

function pieceAtSq(snapshot, sq) {
  if (!snapshot) return null;
  for (const p of snapshot.pieces) {
    if (Number(p.pos) === sq) return p;
  }
  return null;
}

async function refreshLegal() {
  const moves = await api.legal();
  game.setLegal(moves);
  renderer.setLegalMoves(moves);
}

async function syncIntermediateState(snapshot) {
  if (!snapshot) return;
  game.reset(snapshot);
  renderer.syncSnapshot(snapshot);
  renderer.clearSelection();
  await refreshLegal();
  hud.render(game.snapshot, game);
  updateSolarButton();
}

function setDecision(pending) {
  decisionActive = true;
  decisionHighlights = [];
  if (pending && pending.options) {
    for (const o of pending.options) {
      if (o.sq != null) decisionHighlights.push(Number(o.sq));
      if (o.to_sq != null) decisionHighlights.push(Number(o.to_sq));
    }
  }
}

function updateSolarButton() {
  const st = game.snapshot;
  const cfgBySide = st && st.player_config;
  if (!cfgBySide || !st.arcane_state) {
    btnSolar.disabled = true;
    return;
  }
  const stm = st.side_to_move;
  const cfg = cfgBySide[stm];
  const uses = st.arcane_state.solar_uses ? Number(st.arcane_state.solar_uses[stm]) : 0;
  let hasSolar = false;
  if (cfg && cfg.items) {
    for (const item of cfg.items) {
      if (Number(item) === 7) {
        hasSolar = true;
        break;
      }
    }
  }
  btnSolar.disabled = !(hasSolar && uses > 0) || decisionActive || renderer.anim.busy();
}

async function handleServerResponse(resp) {
  if (!resp) return;
  if (resp.pending) {
    if (resp.state) {
      await syncIntermediateState(resp.state);
    }
    setDecision(resp.pending);
    if (!resp.state) {
      renderer.clearSelection();
      hud.render(game.snapshot, game);
      updateSolarButton();
    }
    decisionModal.show(resp.pending, {
      onPick: async (choice) => {
        try {
          const r2 = await api.decide(resp.pending.id, choice);
          await handleServerResponse(r2);
        } catch (e) {
          showError(e);
        }
      },
      onCancel: async () => {
        try {
          const st = await api.cancel();
          decisionModal.hide();
          decisionActive = false;
          decisionHighlights = [];
          game.reset(st);
          renderer.syncSnapshot(st);
          await refreshLegal();
          hud.render(game.snapshot, game);
          updateSolarButton();
          hud.toast("Decision cancelled.");
        } catch (e) {
          showError(e);
        }
      }
    });
    return;
  }

  if (resp.result) {
    decisionModal.hide();
    decisionActive = false;
    decisionHighlights = [];

    const res = resp.result;
    renderer.applyResult(res);
    game.applyResult(res);
    renderer.clearSelection();
    await refreshLegal();
    hud.render(game.snapshot, game);
    updateSolarButton();

    const nm = res.meta && res.meta.result_last_notation ? res.meta.result_last_notation : null;
    if (nm && nm.san) {
      hud.toast(nm.san);
    } else {
      // Solar and other non-move actions can still emit effects.
      const eff = (res.meta && res.meta.effects) ? res.meta.effects : [];
      const lastEff = eff.length ? eff[eff.length - 1] : null;
      if (lastEff && lastEff.type === "solar_topup") {
        hud.toast(`Solar: topped up ${lastEff.kind}`);
      }
    }
  }
}

async function bootstrap() {
  const defs = await api.defs();
  loadout = new LoadoutModal(modalEl, defs);

  const st = await api.state();
  game.reset(st);
  renderer.syncSnapshot(st);
  await refreshLegal();
  hud.render(game.snapshot, game);
  updateSolarButton();
}

function showError(err) {
  console.error(err);
  hud.toast(String(err.message || err));
}

btnNewGame.addEventListener("click", () => {
  loadout.show();
});

btnCloseModal.addEventListener("click", () => loadout.hide());

btnStart.addEventListener("click", async () => {
  try {
    decisionModal.hide();
    decisionActive = false;
    decisionHighlights = [];
    const cfgs = loadout.getConfigs();
    const seed = parseInt(rngSeedEl.value || "1337", 10);
    const st = await api.newGame(cfgs.WHITE, cfgs.BLACK, Number.isFinite(seed) ? seed : 1337);
    game.reset(st);
    renderer.syncSnapshot(st);
    renderer.clearSelection();
    await refreshLegal();
    hud.render(game.snapshot, game);
    updateSolarButton();
    loadout.hide();
    hud.toast("New game started.");
  } catch (e) {
    showError(e);
  }
});

btnSolar.addEventListener("click", async () => {
  if (renderer.anim.busy()) return;
  if (decisionActive) return;
  try {
    solarModal.show(game.snapshot, {
      onPick: async ({ kind, uid }) => {
        const res = await api.solarTopup(kind, uid ?? null);
        solarModal.hide();
        // Treat like a standard result payload.
        renderer.applyResult(res);
        game.applyResult(res);
        await refreshLegal();
        hud.render(game.snapshot, game);
        updateSolarButton();
        const eff = (res.meta && res.meta.effects) ? res.meta.effects : [];
        const lastEff = eff.length ? eff[eff.length - 1] : null;
        if (lastEff && lastEff.type === "solar_topup") hud.toast(`Solar: topped up ${lastEff.kind}`);
      },
      onClose: () => {}
    });
  } catch (e) {
    showError(e);
  }
});

btnUndo.addEventListener("click", async () => {
  if (renderer.anim.busy()) return;
  try {
    if (decisionActive) {
      await api.cancel();
      decisionModal.hide();
      decisionActive = false;
      decisionHighlights = [];
    }
    const res = await api.undo();
    renderer.applyResult(res); // animate reverse-ish diff
    game.applyUndo(res);
    await refreshLegal();
    hud.render(game.snapshot, game);
    updateSolarButton();
  } catch (e) {
    showError(e);
  }
});

btnReset.addEventListener("click", async () => {
  if (renderer.anim.busy()) return;
  try {
    if (decisionActive) {
      await api.cancel();
      decisionModal.hide();
      decisionActive = false;
      decisionHighlights = [];
    }
    const st = await api.reset();
    game.reset(st);
    renderer.syncSnapshot(st);
    renderer.clearSelection();
    await refreshLegal();
    hud.render(game.snapshot, game);
    updateSolarButton();
    hud.toast("Reset.");
  } catch (e) {
    showError(e);
  }
});

qualitySel.addEventListener("change", () => {
  renderer.setQuality(parseInt(qualitySel.value, 10));
});

// Canvas interaction
canvas.addEventListener("mousedown", async (ev) => {
  if (renderer.anim.busy()) return;
  if (decisionActive) return;
  const rect = canvas.getBoundingClientRect();
  const x = ev.clientX - rect.left;
  const y = ev.clientY - rect.top;
  const sq = renderer.squareAtScreen(x, y);
  if (sq == null) return;

  const st = game.snapshot;
  const stm = st.side_to_move;

  const p = pieceAtSq(st, sq);

  if (renderer.selectedSq == null) {
    if (p && p.color === stm) {
      renderer.setSelectionSquare(sq);
      return;
    }
    return;
  }

  // if clicked a legal destination: apply
  if (renderer.destSet.has(sq)) {
    const from = renderer.selectedSq;
    const legal = game.legalMoves;
    const moves = [];
    for (let i = 0; i < legal.length; i += 1) {
      const mv = legal[i];
      if (Number(mv.from) === from && Number(mv.to) === sq) moves.push(mv);
    }
    if (!moves.length) {
      renderer.clearSelection();
      return;
    }
    const chosen = await pickMoveVariant(moves);
    if (!chosen) return;

    try {
      const resp = await api.apply(chosen);
      await handleServerResponse(resp);
    } catch (e) { showError(e); }
    return;
  }

  // click another own piece: switch selection
  if (p && p.color === stm) {
    renderer.setSelectionSquare(sq);
    return;
  }

  renderer.clearSelection();
});

// Resize
const ro = new ResizeObserver(() => {
  const r = canvas.getBoundingClientRect();
  renderer.resize(r.width, r.height);
  renderer.syncSnapshot(game.snapshot);
});
ro.observe(canvas);

// Main loop
let last = performance.now();
let fpsAcc = 0;
let fpsN = 0;
let fpsT = 0;

function loop(now) {
  const dt = now - last;
  last = now;

  renderer.step(dt);

  const st = game.snapshot;
  const checkSq = st && st.check ? findKingSq(st, st.side_to_move) : null;
  renderer.draw(st, { checkSq, highlightSquares: decisionHighlights });

  // FPS sampling
  fpsAcc += 1000 / Math.max(1, dt);
  fpsN++;
  fpsT += dt;
  if (fpsT >= 500) {
    hud.setFPS(fpsAcc / fpsN);
    fpsAcc = 0; fpsN = 0; fpsT = 0;
  }

  requestAnimationFrame(loop);
}

bootstrap().then(() => requestAnimationFrame(loop)).catch(showError);
