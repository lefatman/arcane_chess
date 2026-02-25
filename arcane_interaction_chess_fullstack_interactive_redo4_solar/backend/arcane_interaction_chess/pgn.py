from __future__ import annotations

from typing import Iterable, List, Optional, Tuple

from .core import Game, Move
from .san import to_san


def moves_to_pgn(game: Game, moves: Iterable[Move], headers: Optional[dict] = None) -> str:
    """Serialize a line of play to PGN (minimal).

    This does NOT attempt to parse; it only writes.
    """
    headers = headers or {}
    out_lines: List[str] = []
    for k, v in headers.items():
        out_lines.append(f'[{k} "{v}"]')
    if headers:
        out_lines.append("")

    tokens: List[str] = []
    ply = 0
    for m in moves:
        if ply % 2 == 0:
            # White move number
            move_no = 1 + (ply // 2)
            tokens.append(f"{move_no}.")
        tokens.append(to_san(game, m))
        game.push(m)
        ply += 1

    # Unwind to original
    for _ in range(ply):
        game.pop()

    # Wrap at ~80 chars
    line = ""
    for t in tokens:
        if len(line) + len(t) + 1 > 78:
            out_lines.append(line.rstrip())
            line = ""
        line += t + " "
    if line.strip():
        out_lines.append(line.rstrip())

    return "\n".join(out_lines)
