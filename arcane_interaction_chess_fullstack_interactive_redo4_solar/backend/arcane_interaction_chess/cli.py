from __future__ import annotations

import argparse
from typing import Optional

from .core import Game, setup_standard, ascii_board, PositionTracker
from .fen import parse_fen, game_to_fen, STARTPOS_FEN
from .perft import perft, perft_divide
from .san import to_san
from .engine import Engine
from .uci import move_to_uci


def _uci_to_move(game: Game, uci: str):
    uci = uci.strip().lower()
    for m in game.legal_moves(game.side_to_move):
        if move_to_uci(m) == uci:
            return m
    return None


def _new_game() -> Game:
    g = Game()
    setup_standard(g)
    PositionTracker().attach(g)
    return g


def cmd_perft(args: argparse.Namespace) -> int:
    g = parse_fen(args.fen) if args.fen else _new_game()
    if args.fen:
        PositionTracker().attach(g)
    if args.divide:
        out = perft_divide(g, args.depth)
        total = 0
        for k in sorted(out):
            print(f"{k}: {out[k]}")
            total += out[k]
        print(f"Total: {total}")
    else:
        print(perft(g, args.depth))
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    g = parse_fen(args.fen) if args.fen else _new_game()
    if args.fen:
        PositionTracker().attach(g)
    print(ascii_board(g))
    print()
    print(game_to_fen(g))
    return 0


def cmd_play(args: argparse.Namespace) -> int:
    g = parse_fen(args.fen) if args.fen else _new_game()
    if args.fen:
        PositionTracker().attach(g)
    eng = Engine()
    human = args.human.lower()

    while True:
        print(ascii_board(g))
        print()
        moves = g.legal_moves(g.side_to_move)
        if not moves:
            if g.in_check(g.side_to_move):
                print("Checkmate.")
            else:
                print("Stalemate.")
            return 0

        if (g.side_to_move.name.lower() == human):
            uci = input("Your move (UCI, e.g. e2e4): ").strip()
            if uci in ("quit", "exit"):
                return 0
            m = _uci_to_move(g, uci)
            if m is None:
                print("Illegal move.")
                continue
            print("SAN:", to_san(g, m))
            g.push(m)
        else:
            m = eng.best_move(g, depth=args.depth, time_limit_s=args.movetime)
            if m is None:
                print("Engine has no legal moves.")
                return 0
            print("Engine:", move_to_uci(m), "SAN:", to_san(g, m))
            g.push(m)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="arcane-interaction-chess")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("perft", help="Run perft")
    sp.add_argument("--depth", type=int, default=3)
    sp.add_argument("--fen", type=str, default=None)
    sp.add_argument("--divide", action="store_true")
    sp.set_defaults(fn=cmd_perft)

    ss = sub.add_parser("show", help="Show ASCII board and FEN")
    ss.add_argument("--fen", type=str, default=None)
    ss.set_defaults(fn=cmd_show)

    pl = sub.add_parser("play", help="Play against the built-in engine")
    pl.add_argument("--human", type=str, default="white", choices=["white", "black"])
    pl.add_argument("--depth", type=int, default=3)
    pl.add_argument("--movetime", type=float, default=None, help="seconds")
    pl.add_argument("--fen", type=str, default=None)
    pl.set_defaults(fn=cmd_play)

    args = ap.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
