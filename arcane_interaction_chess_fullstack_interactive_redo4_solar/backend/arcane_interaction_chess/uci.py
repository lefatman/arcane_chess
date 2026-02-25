from __future__ import annotations

import sys
from typing import List, Optional, Tuple

from .core import (
    Game, Color, setup_standard, PositionTracker,
    Move, NormalMove, EnPassantMove, CastleMove, PromotionMove, sq_name
)
from .core import Queen, Rook, Bishop, Knight
from .fen import parse_fen, STARTPOS_FEN
from .engine import Engine


def move_to_uci(m: Move) -> str:
    s = f"{sq_name(m.from_sq)}{sq_name(m.to_sq)}".lower()
    if isinstance(m, PromotionMove):
        promo = m.promote_to
        ch = "q"
        if promo is Rook:
            ch = "r"
        elif promo is Bishop:
            ch = "b"
        elif promo is Knight:
            ch = "n"
        s += ch
    return s


def _uci_to_legal_move(game: Game, uci: str) -> Optional[Move]:
    uci = uci.strip().lower()
    for m in game.legal_moves(game.side_to_move):
        if move_to_uci(m) == uci:
            return m
    return None


def _new_startpos_game() -> Game:
    g = Game()
    setup_standard(g)
    g.halfmove_clock = 0
    g.fullmove_number = 1
    PositionTracker().attach(g)
    return g


def _parse_position(tokens: List[str]) -> Game:
    if not tokens:
        return _new_startpos_game()

    if tokens[0] == "startpos":
        g = _new_startpos_game()
        i = 1
    elif tokens[0] == "fen":
        fen = " ".join(tokens[1:7])
        g = parse_fen(fen)
        PositionTracker().attach(g)
        i = 7
    else:
        g = _new_startpos_game()
        i = 0

    if i < len(tokens) and tokens[i] == "moves":
        for mv in tokens[i + 1 :]:
            m = _uci_to_legal_move(g, mv)
            if m is None:
                break
            g.push(m)
    return g


def main() -> int:
    eng = Engine()
    game = _new_startpos_game()

    while True:
        line = sys.stdin.readline()
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        cmd = parts[0]

        if cmd == "uci":
            print("id name ArcaneInteractionChess")
            print("id author Sashy")
            print("uciok")
            sys.stdout.flush()

        elif cmd == "isready":
            print("readyok")
            sys.stdout.flush()

        elif cmd == "ucinewgame":
            game = _new_startpos_game()
            eng.reset()

        elif cmd == "position":
            game = _parse_position(parts[1:])

        elif cmd == "go":
            depth = 3
            movetime_ms = None
            if "depth" in parts:
                depth = int(parts[parts.index("depth") + 1])
            if "movetime" in parts:
                movetime_ms = int(parts[parts.index("movetime") + 1])
            time_limit = None if movetime_ms is None else movetime_ms / 1000.0
            best = eng.best_move(game, depth=depth, time_limit_s=time_limit)
            if best is None:
                print("bestmove 0000")
            else:
                print(f"bestmove {move_to_uci(best)}")
            sys.stdout.flush()

        elif cmd == "quit":
            break

        else:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
