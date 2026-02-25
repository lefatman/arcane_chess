from __future__ import annotations

from typing import Iterable, Tuple

from .ability import Ability
from .moves import NormalMove, EnPassantMove, PromotionMove, CastleMove, Move
from .types import Color, file_of, rank_of, in_bounds, sq

# deltas
ORTH = ((1,0),(-1,0),(0,1),(0,-1))
DIAG = ((1,1),(1,-1),(-1,1),(-1,-1))
KNIGHT_DELTAS = ((1,2),(2,1),(2,-1),(1,-2),(-1,-2),(-2,-1),(-2,1),(-1,2))
KING8 = ORTH + DIAG

class StepAbility(Ability):
    def __init__(self, deltas: Iterable[Tuple[int,int]]):
        self.deltas = tuple(deltas)

    def generate_moves(self, piece, game):
        f0, r0 = file_of(piece.pos), rank_of(piece.pos)
        for df, dr in self.deltas:
            f, r = f0 + df, r0 + dr
            if not in_bounds(f, r):
                continue
            to = sq(f, r)
            target = game.board.piece_at(to)
            if target is None or target.color != piece.color:
                yield NormalMove(piece.pos, to)

    def generate_attacks(self, piece, game):
        f0, r0 = file_of(piece.pos), rank_of(piece.pos)
        for df, dr in self.deltas:
            f, r = f0 + df, r0 + dr
            if in_bounds(f, r):
                yield sq(f, r)

class SlideAbility(Ability):
    def __init__(self, deltas: Iterable[Tuple[int,int]]):
        self.deltas = tuple(deltas)

    def generate_moves(self, piece, game):
        f0, r0 = file_of(piece.pos), rank_of(piece.pos)
        passthrough = getattr(game, "slide_can_pass_through")(piece)
        for df, dr in self.deltas:
            f, r = f0 + df, r0 + dr
            while in_bounds(f, r):
                to = sq(f, r)
                target = game.board.piece_at(to)
                if target is None:
                    yield NormalMove(piece.pos, to)
                else:
                    if target.color != piece.color:
                        yield NormalMove(piece.pos, to)
                    # stop unless passthrough
                    if not passthrough:
                        break
                f += df
                r += dr

    def generate_attacks(self, piece, game):
        f0, r0 = file_of(piece.pos), rank_of(piece.pos)
        passthrough = getattr(game, "slide_can_pass_through")(piece)
        for df, dr in self.deltas:
            f, r = f0 + df, r0 + dr
            while in_bounds(f, r):
                to = sq(f, r)
                yield to
                if game.board.piece_at(to) is not None and not passthrough:
                    break
                f += df
                r += dr

class PawnAbility(Ability):
    def generate_moves(self, piece, game):
        direction = 1 if piece.color is Color.WHITE else -1
        start_rank = 1 if piece.color is Color.WHITE else 6
        last_rank = 7 if piece.color is Color.WHITE else 0

        f0, r0 = file_of(piece.pos), rank_of(piece.pos)

        # forward 1
        r1 = r0 + direction
        if in_bounds(f0, r1):
            one = sq(f0, r1)
            if game.board.piece_at(one) is None:
                if r1 == last_rank:
                    from .pieces import Queen
                    yield PromotionMove(piece.pos, one, promote_to=Queen)
                else:
                    yield NormalMove(piece.pos, one)

                if r0 == start_rank:
                    r2 = r0 + 2 * direction
                    two = sq(f0, r2)
                    if game.board.piece_at(two) is None:
                        yield NormalMove(piece.pos, two, flags=("double_pawn_push",))

        # captures
        for df in (-1, 1):
            f = f0 + df
            r = r0 + direction
            if not in_bounds(f, r):
                continue
            to = sq(f, r)
            target = game.board.piece_at(to)
            if target is not None and target.color != piece.color:
                if r == last_rank:
                    from .pieces import Queen
                    yield PromotionMove(piece.pos, to, promote_to=Queen)
                else:
                    yield NormalMove(piece.pos, to)

        # en passant
        lm = game.last_move
        if isinstance(lm, NormalMove) and "double_pawn_push" in lm.flags:
            moved_piece = game.board.piece_at(lm.to_sq)
            from .pieces import Pawn
            if moved_piece and isinstance(moved_piece, Pawn) and moved_piece.color != piece.color:
                ep_rank = 4 if piece.color is Color.WHITE else 3
                if rank_of(piece.pos) == ep_rank:
                    if abs(file_of(moved_piece.pos) - f0) == 1 and rank_of(moved_piece.pos) == r0:
                        ep_to = sq(file_of(moved_piece.pos), r0 + direction)
                        if game.board.piece_at(ep_to) is None:
                            yield EnPassantMove(piece.pos, ep_to, captured_sq=moved_piece.pos)

    def generate_attacks(self, piece, game):
        direction = 1 if piece.color is Color.WHITE else -1
        f0, r0 = file_of(piece.pos), rank_of(piece.pos)
        for df in (-1, 1):
            f, r = f0 + df, r0 + direction
            if in_bounds(f, r):
                yield sq(f, r)

class CastleAbility(Ability):
    def generate_moves(self, piece, game):
        from .pieces import Rook
        king = piece
        if king.has_moved:
            return
        if game.in_check(king.color):
            return

        r0 = rank_of(king.pos)
        kf = file_of(king.pos)

        for rook_file in (0, 7):
            rook_sq = sq(rook_file, r0)
            rook = game.board.piece_at(rook_sq)
            if not isinstance(rook, Rook) or rook.color != king.color or rook.has_moved:
                continue

            step = 1 if rook_file > kf else -1

            # corridor empty?
            f = kf + step
            while f != rook_file:
                if game.board.piece_at(sq(f, r0)) is not None:
                    break
                f += step
            else:
                king_to = sq(kf + 2 * step, r0)
                rook_to = sq(kf + 1 * step, r0)

                if game.board.piece_at(king_to) is not None or game.board.piece_at(rook_to) is not None:
                    continue

                enemy = king.color.opponent()
                cross1 = sq(kf + step, r0)
                if game.is_square_attacked(cross1, enemy):
                    continue
                if game.is_square_attacked(king_to, enemy):
                    continue

                yield CastleMove(king.pos, king_to, rook_from=rook.pos, rook_to=rook_to)
