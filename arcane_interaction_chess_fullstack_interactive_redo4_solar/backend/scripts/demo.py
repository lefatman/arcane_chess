from __future__ import annotations

from pathlib import Path
import sys

# Ensure `backend/` is on sys.path so `import arcane_interaction_chess` works.
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from arcane_interaction_chess.core import Color, sq, ascii_board, NormalMove
from arcane_interaction_chess.core.pieces import King, Rook, Pawn, Queen, Bishop
from arcane_interaction_chess.arcane import (
    ArcaneGame,
    PlayerConfig, AbilitySlot,
    ElementId, ItemId, AbilityId,
)


def show(title: str, game: ArcaneGame) -> None:
    print("\n" + "=" * 72)
    print(title)
    print(ascii_board(game))
    print("Side to move:", game.side_to_move)


def demo_chainkill_doublekill_dagger() -> None:
    # White is FIRE -> offensive abilities resolve first
    white = PlayerConfig(
        element=ElementId.FIRE,
        items=[],
        abilities=[
            AbilitySlot(AbilityId.CHAIN_KILL, piece_type="Rook"),
            AbilitySlot(AbilityId.DOUBLE_KILL, piece_type="Rook"),
        ],
    )
    # Needs piece-type targeting: White isn't Lightning, so give Multitasker's Schedule
    white.items = [ItemId.MULTITASKERS_SCHEDULE, ItemId.DUAL_ADEPTS_GLOVES]
    white.validate()

    black = PlayerConfig(
        element=ElementId.AIR,
        items=[ItemId.POISONED_DAGGER],
        abilities=[],
    )

    g = ArcaneGame(white=white, black=black, rng_seed=7)

    # Minimal board
    g.board.add_piece(King(Color.WHITE, sq(4, 0)))  # e1
    g.board.add_piece(King(Color.BLACK, sq(4, 7)))  # e8

    g.board.add_piece(Rook(Color.WHITE, sq(0, 0)))  # a1 (capturer)
    g.board.add_piece(Pawn(Color.WHITE, sq(1, 0)))  # b1 (piggyback origin)

    g.board.add_piece(Queen(Color.BLACK, sq(1, 7)))  # b8 (remote target)
    g.board.add_piece(Pawn(Color.BLACK, sq(0, 7)))   # a8 (neighbor for Double Kill)

    g.bootstrap_resources()

    show("Demo 1: Chain Kill + Double Kill, then Poisoned Dagger kills the capturer (FIRE offense-first)", g)

    # Remote capture: rook at a1 captures b8 as if on b1
    moves = g.legal_moves(Color.WHITE)
    remote = [m for m in moves if m.__class__.__name__ == "RemoteCaptureMove"]
    print("Remote capture moves:", [(m.from_sq, m.to_sq, getattr(m, "origin_sq", None)) for m in remote])

    g.push(remote[0])

    show("After remote capture resolution", g)
    print("Graveyard WHITE:", [(type(p).__name__, s) for (p, s) in g.arcane_state.graveyard[Color.WHITE]])
    print("Graveyard BLACK:", [(type(p).__name__, s) for (p, s) in g.arcane_state.graveyard[Color.BLACK]])


def demo_air_slides_through() -> None:
    white = PlayerConfig(element=ElementId.AIR, items=[], abilities=[])
    black = PlayerConfig(element=ElementId.FIRE, items=[], abilities=[])

    g = ArcaneGame(white=white, black=black)

    g.board.add_piece(King(Color.WHITE, sq(4, 0)))
    g.board.add_piece(King(Color.BLACK, sq(4, 7)))

    g.board.add_piece(Bishop(Color.WHITE, sq(2, 0)))  # c1
    g.board.add_piece(Pawn(Color.WHITE, sq(3, 1)))    # d2 blocks normally

    g.bootstrap_resources()

    show("Demo 2: AIR bishop can slide 'through' a blocker", g)
    ms = [m for m in g.legal_moves(Color.WHITE) if isinstance(m, NormalMove) and m.from_sq == sq(2, 0)]
    print("Bishop moves from c1:", sorted(ms, key=lambda m: m.to_sq))


def demo_redo_rewinds_two_plies() -> None:
    # White has REDO on pawns (Water doubles to 2 charges because Black is not Lightning)
    white = PlayerConfig(
        element=ElementId.WATER,
        items=[ItemId.MULTITASKERS_SCHEDULE],
        abilities=[AbilitySlot(AbilityId.REDO, piece_type="Pawn")],
    )
    black = PlayerConfig(element=ElementId.FIRE, items=[], abilities=[])

    g = ArcaneGame(white=white, black=black)

    g.board.add_piece(King(Color.WHITE, sq(4, 0)))
    g.board.add_piece(King(Color.BLACK, sq(4, 7)))

    wp = Pawn(Color.WHITE, sq(4, 1))  # e2 (redo)
    g.board.add_piece(wp)
    g.board.add_piece(Rook(Color.BLACK, sq(4, 3)))  # e4

    g.bootstrap_resources()

    show("Demo 3: REDO triggers on capture and rewinds 2 plies", g)
    print("Redo charges for e2 pawn:", g.arcane_state.redo_charges.get(wp.uid))

    g.push(NormalMove(sq(4, 1), sq(4, 2)))
    show("After White plays e2-e3", g)

    g.push(NormalMove(sq(4, 3), sq(4, 2)))
    show("After Black attempts capture (Redo should have rewound and forced White to replay)", g)


if __name__ == "__main__":
    demo_chainkill_doublekill_dagger()
    demo_air_slides_through()
    demo_redo_rewinds_two_plies()
