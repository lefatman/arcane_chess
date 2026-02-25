export class GameState {
  constructor() {
    this.snapshot = null;
    this.legalMoves = [];
    this.effects = [];
    this.moveHistory = []; // {ply, san, uci}
  }

  reset(snapshot) {
    this.snapshot = snapshot;
    this.legalMoves = [];
    this.effects = [];
    this.moveHistory = [];
  }

  setLegal(moves) {
    this.legalMoves = moves || [];
  }

  applyResult(res) {
    this.snapshot = res.after;
    this.effects = (res.meta && res.meta.effects) ? res.meta.effects : [];

    const last = res.meta && res.meta.result_last_notation ? res.meta.result_last_notation : null;
    if (last && last.san) {
      const ply = this.snapshot.ply;
      this.moveHistory.push({ ply, san: last.san, uci: last.uci });
    }
  }

  applyUndo(res) {
    this.snapshot = res.after;
    this.effects = (res.meta && res.meta.undone && res.meta.undone.effects) ? res.meta.undone.effects : [];
    // crude: pop last move
    this.moveHistory.pop();
  }
}
