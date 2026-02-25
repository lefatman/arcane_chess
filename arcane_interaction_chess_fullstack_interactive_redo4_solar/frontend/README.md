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
