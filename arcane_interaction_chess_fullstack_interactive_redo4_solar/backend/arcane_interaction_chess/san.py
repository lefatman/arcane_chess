from __future__ import annotations

from typing import List, Optional, Tuple, Type

from .core import (
    Game, Color, Move,
    NormalMove, EnPassantMove, CastleMove, PromotionMove,
    sq_name, file_of, rank_of,
    Pawn, Knight, Bishop, Rook, Queen, King,
)


_PIECE_LETTER = {
    King: "K",
    Queen: "Q",
    Rook: "R",
    Bishop: "B",
    Knight: "N",
    Pawn: "",
}


def _promotion_letter(cls: Type) -> str:
    if cls is Queen:
        return "Q"
    if cls is Rook:
        return "R"
    if cls is Bishop:
        return "B"
    if cls is Knight:
        return "N"
    return "Q"


def to_san(game: Game, move: Move) -> str:
    """Convert a legal move to SAN.

    For arcane-specific move kinds (e.g. remote_capture), this falls back to UCI-ish notation.
    """
    # Castling
    if isinstance(move, CastleMove):
        san = "O-O" if file_of(move.to_sq) == 6 else "O-O-O"
        # check/mate suffix
        game.push_quiet(move)
        suffix = _check_suffix(game)
        game.pop_quiet()
        return san + suffix

    mover = game.board.piece_at(move.from_sq)
    if mover is None:
        raise ValueError("Move has no mover on from_sq")

    mover_cls = type(mover)
    piece_letter = _PIECE_LETTER.get(mover_cls, mover_cls.__name__[0].upper())

    # capture detection (before applying)
    is_capture = game.board.piece_at(move.to_sq) is not None or isinstance(move, EnPassantMove)

    # disambiguation for non-pawns
    disamb = ""
    if mover_cls is not Pawn and mover_cls is not King:
        disamb = _disambiguation(game, move, mover_cls, mover.color)

    dest = sq_name(move.to_sq)

    if mover_cls is Pawn:
        if is_capture:
            origin_file = "abcdefgh"[file_of(move.from_sq)]
            san = f"{origin_file}x{dest}"
        else:
            san = dest
    else:
        san = f"{piece_letter}{disamb}{'x' if is_capture else ''}{dest}"

    # promotion
    if isinstance(move, PromotionMove):
        san += "=" + _promotion_letter(move.promote_to)

    # check/mate
    game.push_quiet(move)
    san += _check_suffix(game)
    game.pop_quiet()
    return san


def _check_suffix(game_after_move: Game) -> str:
    # After applying a move, side_to_move has flipped.
    side = game_after_move.side_to_move
    in_check = game_after_move.in_check(side)
    if not in_check:
        return ""
    replies = game_after_move.legal_moves(side)
    return "#" if len(replies) == 0 else "+"


def _disambiguation(game: Game, move: Move, mover_cls: Type, color: Color) -> str:
    candidates = []
    for m in game.legal_moves(color):
        if m is move:
            continue
        if m.to_sq != move.to_sq:
            continue
        p = game.board.piece_at(m.from_sq)
        if p is None or type(p) is not mover_cls:
            continue
        candidates.append(m)

    if not candidates:
        return ""

    # Include current mover in the pool for uniqueness tests
    all_from = [move.from_sq] + [m.from_sq for m in candidates]
    files = [file_of(s) for s in all_from]
    ranks = [rank_of(s) for s in all_from]

    my_file = file_of(move.from_sq)
    my_rank = rank_of(move.from_sq)

    if files.count(my_file) == 1:
        return "abcdefgh"[my_file]
    if ranks.count(my_rank) == 1:
        return str(my_rank + 1)
    return f"{'abcdefgh'[my_file]}{my_rank + 1}"
