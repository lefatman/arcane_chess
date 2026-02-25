from __future__ import annotations

import random
from typing import Dict, List, Optional, Tuple

from .types import Color, file_of, sq
from .events import MoveWillApply, MoveApplied, MoveUndone
from .game import Listener
from .moves import Move, NormalMove, EnPassantMove, CastleMove, PromotionMove
from .pieces import Pawn, Knight, Bishop, Rook, Queen, King

class PositionTracker(Listener):
    """Zobrist hash + repetition + lazy attacked-squares cache."""

    PIECE_ORDER = (Pawn, Knight, Bishop, Rook, Queen, King)

    def __init__(self, seed: int = 0xC0FFEE) -> None:
        rng = random.Random(seed)

        self.psq = [
            [[rng.getrandbits(64) for _ in range(64)] for _ in range(6)],
            [[rng.getrandbits(64) for _ in range(64)] for _ in range(6)],
        ]
        self.side_key = rng.getrandbits(64)
        self.castle_keys = {1: rng.getrandbits(64), 2: rng.getrandbits(64), 4: rng.getrandbits(64), 8: rng.getrandbits(64)}
        self.ep_file_keys = [rng.getrandbits(64) for _ in range(8)]

        self.hash: int = 0
        self.castle_rights: int = 0
        self.ep_file: Optional[int] = None

        self.rep: Dict[int, int] = {}
        self._stack: List[Tuple[int, int, Optional[int], Optional[int]]] = []

        self._att_dirty = True
        self._att_bb: Dict[Color, int] = {Color.WHITE: 0, Color.BLACK: 0}

    def attach(self, game) -> None:
        game.listeners.append(self)
        game.tracker = self
        self.sync_from_board(game)

    def is_threefold(self) -> bool:
        return self.rep.get(self.hash, 0) >= 3

    def attacked_bb(self, game, by_color: Color) -> int:
        if self._att_dirty:
            self._rebuild_attack_cache(game)
        return self._att_bb[by_color]

    def on_event(self, game, event: object) -> None:
        if isinstance(event, MoveWillApply):
            self._stack.append((self.hash, self.castle_rights, self.ep_file, None))
        elif isinstance(event, MoveApplied):
            self._apply_move_update(game, event.move, event.mover, event.captured)
            pre_hash, pre_c, pre_ep, _ = self._stack[-1]
            self._stack[-1] = (pre_hash, pre_c, pre_ep, self.hash)
            self.rep[self.hash] = self.rep.get(self.hash, 0) + 1
            self._att_dirty = True
        elif isinstance(event, MoveUndone):
            pre_hash, pre_c, pre_ep, post_hash = self._stack.pop()
            if post_hash is not None:
                self.rep[post_hash] = self.rep.get(post_hash, 0) - 1
                if self.rep[post_hash] <= 0:
                    self.rep.pop(post_hash, None)
            self.hash = pre_hash
            self.castle_rights = pre_c
            self.ep_file = pre_ep
            self._att_dirty = True

    def sync_from_board(self, game) -> None:
        self.castle_rights = self._compute_castle_rights(game)
        self.ep_file = self._compute_ep_file(game)
        self.hash = self.compute_hash(game)
        self.rep = {self.hash: 1}
        self._stack.clear()
        self._att_dirty = True

    def compute_hash(self, game) -> int:
        h = 0
        for p in game.board._pieces.values():
            h ^= self._psq_key(p, p.pos)
        if game.side_to_move is Color.BLACK:
            h ^= self.side_key
        h ^= self._castle_hash(self.castle_rights)
        if self.ep_file is not None:
            h ^= self.ep_file_keys[self.ep_file]
        return h

    def _color_index(self, c: Color) -> int:
        return 0 if c is Color.WHITE else 1

    def _piece_index(self, p) -> int:
        t = type(p)
        for i, cls in enumerate(self.PIECE_ORDER):
            if t is cls:
                return i
        raise ValueError(f"Unknown piece type: {t}")

    def _psq_key(self, p, square: int) -> int:
        return self.psq[self._color_index(p.color)][self._piece_index(p)][square]

    def _castle_hash(self, rights: int) -> int:
        h = 0
        for bit, key in self.castle_keys.items():
            if rights & bit:
                h ^= key
        return h

    def _compute_ep_file(self, game) -> Optional[int]:
        lm = game.last_move
        if isinstance(lm, NormalMove) and "double_pawn_push" in lm.flags:
            return file_of(lm.to_sq)
        return None

    def _compute_castle_rights(self, game) -> int:
        rights = 0

        def ok_king(color: Color, s: int) -> bool:
            p = game.board.piece_at(s)
            return isinstance(p, King) and p.color is color and not p.has_moved

        def ok_rook(color: Color, s: int) -> bool:
            p = game.board.piece_at(s)
            return isinstance(p, Rook) and p.color is color and not p.has_moved

        e1 = sq(4, 0); a1 = sq(0, 0); h1 = sq(7, 0)
        e8 = sq(4, 7); a8 = sq(0, 7); h8 = sq(7, 7)

        if ok_king(Color.WHITE, e1):
            if ok_rook(Color.WHITE, h1): rights |= 1
            if ok_rook(Color.WHITE, a1): rights |= 2
        if ok_king(Color.BLACK, e8):
            if ok_rook(Color.BLACK, h8): rights |= 4
            if ok_rook(Color.BLACK, a8): rights |= 8
        return rights

    def _apply_move_update(self, game, move: Move, mover, captured) -> None:
        # remove previous ep/castle
        h = self.hash
        h ^= self._castle_hash(self.castle_rights)
        if self.ep_file is not None:
            h ^= self.ep_file_keys[self.ep_file]

        # toggle side
        h ^= self.side_key

        # treat RemoteCaptureMove specially by name (avoid arcane import)
        if move.__class__.__name__ == "RemoteCaptureMove":
            # attacker doesn't move; only remove captured (if any)
            if captured is not None:
                h ^= self._psq_key(captured, move.to_sq)
            # castle/ep recompute
            self.castle_rights = self._compute_castle_rights(game)
            self.ep_file = self._compute_ep_file(game)

            h ^= self._castle_hash(self.castle_rights)
            if self.ep_file is not None:
                h ^= self.ep_file_keys[self.ep_file]
            self.hash = h
            return

        if isinstance(move, CastleMove):
            h ^= self._psq_key(mover, move.from_sq)
            h ^= self._psq_key(mover, move.to_sq)
            tmp_rook = Rook(mover.color, move.rook_from)
            h ^= self._psq_key(tmp_rook, move.rook_from)
            h ^= self._psq_key(tmp_rook, move.rook_to)

        elif isinstance(move, EnPassantMove):
            h ^= self._psq_key(mover, move.from_sq)
            h ^= self._psq_key(mover, move.to_sq)
            if captured is not None:
                h ^= self._psq_key(captured, move.captured_sq)

        elif isinstance(move, PromotionMove):
            h ^= self._psq_key(mover, move.from_sq)
            if captured is not None:
                h ^= self._psq_key(captured, move.to_sq)
            promoted = move.promote_to(mover.color, move.to_sq)  # type: ignore[misc]
            h ^= self._psq_key(promoted, move.to_sq)

        elif isinstance(move, NormalMove):
            h ^= self._psq_key(mover, move.from_sq)
            if captured is not None:
                h ^= self._psq_key(captured, move.to_sq)
            h ^= self._psq_key(mover, move.to_sq)

        else:
            # unknown move class: safe recompute
            self.castle_rights = self._compute_castle_rights(game)
            self.ep_file = self._compute_ep_file(game)
            self.hash = self.compute_hash(game)
            return

        # update rights + ep
        self.castle_rights = self._compute_castle_rights(game)
        self.ep_file = self._compute_ep_file(game)

        h ^= self._castle_hash(self.castle_rights)
        if self.ep_file is not None:
            h ^= self.ep_file_keys[self.ep_file]

        self.hash = h

    def _rebuild_attack_cache(self, game) -> None:
        bbw = 0
        bbb = 0
        for p in game.board._pieces.values():
            bb = 0
            for a in p.attacks(game):
                bb |= (1 << a)
            if p.color is Color.WHITE:
                bbw |= bb
            else:
                bbb |= bb
        self._att_bb[Color.WHITE] = bbw
        self._att_bb[Color.BLACK] = bbb
        self._att_dirty = False
