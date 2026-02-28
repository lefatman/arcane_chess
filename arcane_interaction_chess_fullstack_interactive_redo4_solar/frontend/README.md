# Frontend (procedural 2.5D)

This directory is **drop-in**: it can live beside `backend/` without requiring changes elsewhere.

## What you get
- A **stdlib-only** Python dev server (`frontend/server.py`) that serves:
  - the static frontend (`index.html`, `style.css`, `src/*`)
  - a JSON API wrapping the backend `ArcaneEngine`
- A **vanilla JS** client with a procedural **2.5D, cell-shaded** isometric renderer:
  - no sprites
  - no textures
  - pieces are generated at runtime as cel-shaded prisms + minimalist glyphs
- A New Game modal to configure **elements/items/abilities** (backend enforces rules)

## Run
From repo root:

```bash
python frontend/server.py
```

Then open:
- `http://127.0.0.1:8000/`

## Controls
- Click your piece → highlights legal destinations
- Click a highlighted destination → move
- **Undo** reverses one ply
- **New game** opens loadout configuration

## API (for future frontend work)
- `GET /api/defs`
- `GET /api/state`
- `GET /api/legal`
- `POST /api/apply` `{ move: <move-dict-from-legal> }`
- `POST /api/undo`
- `POST /api/reset`
- `POST /api/newgame` `{ white: {...}, black: {...}, rng_seed }`

> Note: the backend currently uses a default deterministic decision provider for arcane choices
> (Block Path direction, Redo replay, etc.). The API surface is intentionally small so we can
> add interactive decision prompts next.


## Snapshot contract used by UI
The UI reads these `GET /api/state` snapshot fields directly:

- `side_to_move`: active side (`"WHITE"`/`"BLACK"`)
- `pieces[]`: each piece uses `uid`, `color`, `type`, `pos`, `pos_alg`
- `player_config`: per-side arcane loadout keyed by side (`WHITE`/`BLACK`)
  - `element`, `element_id`, `items[]`, `abilities[]`
- `arcane_state`: runtime arcane pools/charges
  - `solar_uses`, `solar_max`, `necro_pool`, `necro_max`, `redo_charges`, `redo_max`, `graveyard`
- `check`, `checkmate`, `fen`, `ply`

Notes:
- `player_config` is the canonical arcane config key for frontend readers.
- The backend may also emit legacy `arcane` temporarily for backward compatibility; UI code should rely on `player_config`.
