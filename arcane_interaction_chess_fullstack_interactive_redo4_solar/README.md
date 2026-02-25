# Arcane Interaction Chess (backend)

This is the **Python backend** for the Interaction-driven Chess engine + the Arcane layer (Elements / Items / Abilities).

Key properties:
- **Rules emerge from piece abilities** (movement, attacks, special moves).
- **Rules pipeline** filters pseudo-legal moves (King safety, capture defense, Chain Kill, etc.).
- **Event bus** + deterministic `push/pop` for full reversibility.
- Arcane layer implements your canonical tables: **Elements**, **Items**, **Abilities** (Redo, Chain Kill, Necromancer, etc.).

## Frontend slotting
A future browser frontend can be added as a sibling directory (`frontend/`) without changing backend files.
The backend exposes a stable boundary in `backend/arcane_interaction_chess/api/`:
- JSON-friendly **state snapshots**
- JSON-friendly **move encoding/decoding**
- deterministic apply/undo
- per-move **diff** (added/removed/moved pieces) for animation
- per-move **meta** including SAN/UCI notation and an **effects log** (Redo, Poisoned Dagger, Double/Quantum Kill, Necromancer, Block Path, Lightning misfire)

## Quick start
```bash
python backend/scripts/demo.py
```

## API usage (minimal)
```python
from backend.arcane_interaction_chess.api.facade import ArcaneEngine

engine = ArcaneEngine.standard_demo_game()
state = engine.state()
moves = engine.legal_moves()  # list[dict]
engine.apply(moves[0])
```


## Formats & tools
The backend now includes baseline-chess helpers (usable with the core `Game`, and compatible with `ArcaneGame` when arcane powers are disabled):

- **FEN**: `arcane_interaction_chess.fen.parse_fen`, `game_to_fen`
- **SAN**: `arcane_interaction_chess.san.to_san`
- **PGN writer**: `arcane_interaction_chess.pgn.moves_to_pgn`
- **Perft**: `arcane_interaction_chess.perft.perft`, `perft_divide`
- **UCI**: `python -m arcane_interaction_chess.uci` (baseline chess)

### CLI
From the repo root (adds `backend/` to import path):
```bash
PYTHONPATH=backend python -m arcane_interaction_chess show
PYTHONPATH=backend python -m arcane_interaction_chess perft --depth 3
PYTHONPATH=backend python -m arcane_interaction_chess play --human white --depth 3
```

### Run tests
```bash
python backend/scripts/run_tests.py
```

### Benchmarks (hot-path tracking)
From the repo root:
```bash
PYTHONPATH=backend python backend/scripts/benchmark_hotpaths.py
```

To run periodic regression checks against `backend/scripts/benchmark_thresholds.json` (recommended on a schedule, not per-PR due to machine noise):
```bash
PYTHONPATH=backend python backend/scripts/benchmark_hotpaths.py --check-thresholds
```
