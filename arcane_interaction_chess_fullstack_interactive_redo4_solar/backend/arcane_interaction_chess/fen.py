from __future__ import annotations

from typing import Dict, Optional, Tuple, Type

from .core import (
    Game, Color, sq, sq_name, file_of, rank_of,
    NormalMove, EnPassantMove, PromotionMove, CastleMove,
    Pawn, Knight, Bishop, Rook, Queen, King,
)

STARTPOS_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

_PIECE_CHARS: Dict[Type, str] = {
    Pawn: "p",
    Knight: "n",
    Bishop: "b",
    Rook: "r",
    Queen: "q",
    King: "k",
}
_CHAR_TO_PIECE: Dict[str, Type] = {v: k for k, v in _PIECE_CHARS.items()}


def _alg_to_sq(a: str) -> int:
    a = a.strip().lower()
    if len(a) != 2:
        raise ValueError(f"Bad square: {a!r}")
    f = ord(a[0]) - ord("a")
    r = int(a[1]) - 1
    if not (0 <= f < 8 and 0 <= r < 8):
        raise ValueError(f"Bad square: {a!r}")
    return sq(f, r)


def parse_fen(fen: str) -> Game:
    """Parse standard chess FEN into a core.Game.

    Note: Arcane loadouts are not represented in FEN; this builds a baseline chess state.
    """
    parts = fen.strip().split()
    if len(parts) != 6:
        raise ValueError("FEN must have 6 fields")

    placement, stm, castling, ep, halfmove, fullmove = parts

    g = Game()

    ranks = placement.split("/")
    if len(ranks) != 8:
        raise ValueError("FEN placement must have 8 ranks")

    white_kings = 0
    black_kings = 0

    for rank_idx, row in enumerate(ranks):
        r = 7 - rank_idx
        f = 0
        for ch in row:
            if ch.isdigit():
                gap = int(ch)
                if gap < 1 or gap > 8:
                    raise ValueError("Bad empty-square run in FEN")
                f += gap
                if f > 8:
                    raise ValueError("Bad rank width in FEN")
                continue
            if f >= 8:
                raise ValueError("Bad rank width in FEN")
            color = Color.WHITE if ch.isupper() else Color.BLACK
            kind = _CHAR_TO_PIECE.get(ch.lower())
            if kind is None:
                raise ValueError(f"Unknown piece char: {ch}")
            pos = sq(f, r)
            g.board.add_piece(kind(color, pos))  # type: ignore[misc]
            if kind is King:
                if color is Color.WHITE:
                    white_kings += 1
                else:
                    black_kings += 1
            f += 1
        if f != 8:
            raise ValueError("Bad rank width in FEN")

    if white_kings != 1 or black_kings != 1:
        raise ValueError("FEN must contain exactly one king per side")

    if stm == "w":
        g.side_to_move = Color.WHITE
    elif stm == "b":
        g.side_to_move = Color.BLACK
    else:
        raise ValueError("Bad side-to-move in FEN")

    g.halfmove_clock = int(halfmove)
    g.fullmove_number = int(fullmove)

    # Castling rights -> infer has_moved flags on home king/rooks
    wk = g.board.piece_at(_alg_to_sq("e1"))
    bk = g.board.piece_at(_alg_to_sq("e8"))
    wra = g.board.piece_at(_alg_to_sq("a1"))
    wrh = g.board.piece_at(_alg_to_sq("h1"))
    bra = g.board.piece_at(_alg_to_sq("a8"))
    brh = g.board.piece_at(_alg_to_sq("h8"))

    # If king/rook aren't on home squares, castling is already impossible => mark moved.
    for p in (wk, bk):
        if isinstance(p, King) and ((p.color is Color.WHITE and p.pos != _alg_to_sq("e1")) or (p.color is Color.BLACK and p.pos != _alg_to_sq("e8"))):
            p.has_moved = True

    if castling == "-":
        castling = ""
    else:
        seen = set()
        for flag in castling:
            if flag not in "KQkq":
                raise ValueError("Bad castling rights in FEN")
            if flag in seen:
                raise ValueError("Bad castling rights in FEN")
            seen.add(flag)

    def _expect(piece, piece_type, color: Color) -> bool:
        return isinstance(piece, piece_type) and piece.color is color

    if "K" in castling and not (_expect(wk, King, Color.WHITE) and _expect(wrh, Rook, Color.WHITE)):
        raise ValueError("Bad castling rights in FEN")
    if "Q" in castling and not (_expect(wk, King, Color.WHITE) and _expect(wra, Rook, Color.WHITE)):
        raise ValueError("Bad castling rights in FEN")
    if "k" in castling and not (_expect(bk, King, Color.BLACK) and _expect(brh, Rook, Color.BLACK)):
        raise ValueError("Bad castling rights in FEN")
    if "q" in castling and not (_expect(bk, King, Color.BLACK) and _expect(bra, Rook, Color.BLACK)):
        raise ValueError("Bad castling rights in FEN")

    def _set_if(piece, allowed: bool):
        if piece is not None:
            piece.has_moved = not allowed

    _set_if(wk, "K" in castling or "Q" in castling)  # if any white rights, king must be unmoved
    _set_if(bk, "k" in castling or "q" in castling)
    _set_if(wrh, "K" in castling)
    _set_if(wra, "Q" in castling)
    _set_if(brh, "k" in castling)
    _set_if(bra, "q" in castling)

    # En passant: synthesize last move as a double pawn push, so EP generation works.
    if ep != "-" and ep:
        ep_sq = _alg_to_sq(ep)
        ep_rank = rank_of(ep_sq)
        if g.side_to_move is Color.WHITE:
            if ep_rank != 5:
                raise ValueError("Bad en-passant square in FEN")
            # black moved last; pawn is one rank below ep square
            to_sq = ep_sq - 8
            from_sq = to_sq + 16
            expected_color = Color.BLACK
        else:
            if ep_rank != 2:
                raise ValueError("Bad en-passant square in FEN")
            # white moved last
            to_sq = ep_sq + 8
            from_sq = to_sq - 16
            expected_color = Color.WHITE

        if not (0 <= from_sq < 64 and 0 <= to_sq < 64):
            raise ValueError("Bad en-passant square in FEN")

        if g.board.piece_at(ep_sq) is not None:
            raise ValueError("Bad en-passant square in FEN")

        if g.board.piece_at(from_sq) is not None:
            raise ValueError("Bad en-passant square in FEN")

        pawn = g.board.piece_at(to_sq)
        if not isinstance(pawn, Pawn) or pawn.color is not expected_color:
            raise ValueError("Bad en-passant square in FEN")

        g.last_move = NormalMove(from_sq=from_sq, to_sq=to_sq, flags=("double_pawn_push",))

    return g


def game_to_fen(g: Game) -> str:
    # placement
    rows = []
    for r in range(7, -1, -1):
        empty = 0
        row = []
        for f in range(8):
            p = g.board.piece_at(sq(f, r))
            if p is None:
                empty += 1
                continue
            if empty:
                row.append(str(empty))
                empty = 0
            ch = _PIECE_CHARS.get(type(p))
            if ch is None:
                # unknown piece class; fall back to symbol lower
                ch = getattr(p, "symbol", "?").lower()
            row.append(ch.upper() if p.color is Color.WHITE else ch.lower())
        if empty:
            row.append(str(empty))
        rows.append("".join(row))
    placement = "/".join(rows)

    stm = "w" if g.side_to_move is Color.WHITE else "b"

    # castling rights from has_moved flags on home pieces
    rights = []
    wk = g.board.piece_at(_alg_to_sq("e1"))
    bk = g.board.piece_at(_alg_to_sq("e8"))
    wra = g.board.piece_at(_alg_to_sq("a1"))
    wrh = g.board.piece_at(_alg_to_sq("h1"))
    bra = g.board.piece_at(_alg_to_sq("a8"))
    brh = g.board.piece_at(_alg_to_sq("h8"))

    if isinstance(wk, King) and not wk.has_moved:
        if isinstance(wrh, Rook) and not wrh.has_moved:
            rights.append("K")
        if isinstance(wra, Rook) and not wra.has_moved:
            rights.append("Q")
    if isinstance(bk, King) and not bk.has_moved:
        if isinstance(brh, Rook) and not brh.has_moved:
            rights.append("k")
        if isinstance(bra, Rook) and not bra.has_moved:
            rights.append("q")

    castling = "".join(rights) if rights else "-"

    # en passant from last move if it was a double pawn push
    ep = "-"
    lm = g.last_move
    if isinstance(lm, NormalMove) and "double_pawn_push" in (lm.flags or ()):
        moved = g.board.piece_at(lm.to_sq)
        # If the pawn is still on its to-square, we can compute EP target
        if isinstance(moved, Pawn):
            if moved.color is Color.WHITE:
                ep_sq = lm.to_sq - 8
            else:
                ep_sq = lm.to_sq + 8
            if 0 <= ep_sq < 64:
                ep = sq_name(ep_sq)

    halfmove = str(int(getattr(g, "halfmove_clock", 0)))
    fullmove = str(int(getattr(g, "fullmove_number", 1)))

    return f"{placement} {stm} {castling} {ep} {halfmove} {fullmove}"
