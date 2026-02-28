export class ApiClient {
  constructor(base = "") {
    this.base = base;
  }

  async _get(path) {
    const r = await fetch(this.base + path, { cache: "no-store" });
    const j = await r.json();
    if (!j.ok) throw new Error(j.error || `HTTP ${r.status}`);
    return j;
  }

  async _post(path, body) {
    const r = await fetch(this.base + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body ?? {}),
    });
    const j = await r.json();
    if (!j.ok) throw new Error(j.error || `HTTP ${r.status}`);
    return j;
  }

  defs() { return this._get("/api/defs").then(x => x.defs); }
  state() { return this._get("/api/state").then(x => x.state); }
  legal() { return this._get("/api/legal").then(x => x.moves); }

  apply(moveDict) { return this._post("/api/apply", { move: moveDict }); }
  decide(id, choice) { return this._post("/api/decide", { id, choice }); }
  pending() { return this._get("/api/pending"); }
  cancel() { return this._post("/api/cancel", {}).then(x => x.state); }
  undo() { return this._post("/api/undo", {}).then(x => x.result); }
  reset() { return this._post("/api/reset", {}).then(x => x.state); }
  newGame(whiteCfg, blackCfg, rngSeed = 1337) {
    return this._post("/api/newgame", { white: whiteCfg, black: blackCfg, rng_seed: rngSeed }).then(x => x.state);
  }

  solarTopup(kind, uid = null) {
    return this._post("/api/solar_topup", { kind, uid }).then(x => x.result);
  }
}
