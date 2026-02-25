from __future__ import annotations

from typing import Iterable, List, Optional, TYPE_CHECKING

from .types import Color
from .board import Board
from .moves import Move, Undo
from .events import MoveWillApply, MoveApplied, MoveUndone
from .rules import Rule, KingSafetyRule

class Listener:
    def on_event(self, game: "Game", event: object) -> None:
        return

class Game:
    def __init__(self) -> None:
        self.board = Board()
        self.side_to_move: Color = Color.WHITE
        self.last_move: Optional[Move] = None
        self._stack: List[Undo] = []

        # clocks (for FEN/PGN/UCI friendliness)
        self.halfmove_clock: int = 0
        self.fullmove_number: int = 1

        self.rules: List[Rule] = [KingSafetyRule()]
        self.listeners: List[Listener] = []

        # optional tracker; set by tracker.attach
        self.tracker = None

    # --- extension hooks (override in subclasses) ---
    def _after_apply(self, undo: Undo) -> None:
        return

    def _after_unapply(self, undo: Undo) -> None:
        return

    # --- movement-modifier hook (Air/Wind) ---
    def slide_can_pass_through(self, mover: "Piece") -> bool:
        return False


    # --- clocks ---
    def _update_clocks_after_apply(self, undo: Undo) -> None:
        # Snapshot previous clocks into undo.extras (reusable by all move types)
        undo.extras.setdefault("prev_halfmove_clock", self.halfmove_clock)
        undo.extras.setdefault("prev_fullmove_number", self.fullmove_number)

        mover = undo.mover
        is_capture = undo.captured_piece is not None

        # Pawn move detection without importing pieces at module load
        is_pawn = False
        if mover is not None:
            # Pawn symbols are 'P'/'p'
            if getattr(mover, "symbol", "") in ("P", "p"):
                is_pawn = True

        if is_capture or is_pawn:
            self.halfmove_clock = 0
        else:
            self.halfmove_clock += 1

        # Fullmove increments after Black has played (i.e., previous side was Black)
        if undo.prev_side is Color.BLACK:
            self.fullmove_number += 1

    def _restore_clocks(self, undo: Undo) -> None:
        self.halfmove_clock = int(undo.extras.get("prev_halfmove_clock", 0))
        self.fullmove_number = int(undo.extras.get("prev_fullmove_number", 1))

    def emit(self, event: object) -> None:
        for sys in list(self.listeners):
            sys.on_event(self, event)
        for p in list(self.board._pieces.values()):
            p.on_event(self, event)

    def push(self, move: Move) -> None:
        mover = self.board.piece_at(move.from_sq)
        if mover is None:
            raise ValueError("No piece on from-square")

        self.emit(MoveWillApply(move=move, mover=mover))
        undo = move.apply(self)
        self._stack.append(undo)
        self._update_clocks_after_apply(undo)

        self._after_apply(undo)
        self.emit(MoveApplied(move=move, mover=undo.mover, captured=undo.captured_piece))

    def pop(self) -> None:
        undo = self._stack.pop()

        # restore basic state
        self.side_to_move = undo.prev_side
        self.last_move = undo.prev_last_move
        self._restore_clocks(undo)
        if self.tracker is not None:
            self.tracker._att_dirty = True

        # remove added pieces (promotion / resurrect etc)
        for p in undo.added:
            self.board.remove_piece(p.pos)

        # restore removed pieces
        for p, pos, hm in undo.removed:
            p.pos = pos
            p.has_moved = hm
            self.board._pieces[pos] = p

        # restore captured pieces
        for p, pos, hm in undo.captured:
            p.pos = pos
            p.has_moved = hm
            self.board._pieces[pos] = p

        # restore moved pieces
        for p, pos, hm in undo.changed:
            for k, v in list(self.board._pieces.items()):
                if v is p and k != pos:
                    self.board._pieces.pop(k, None)
                    break
            p.pos = pos
            p.has_moved = hm
            self.board._pieces[pos] = p

        # restore per-piece meta dicts
        for p, meta in undo.piece_meta_snapshots:
            p.meta = meta

        self._after_unapply(undo)
        if undo.move is not None and undo.mover is not None:
            self.emit(MoveUndone(move=undo.move, mover=undo.mover, captured=undo.captured_piece))

    # quiet versions: no events, no hooks, used for legality checks
    def push_quiet(self, move: Move) -> None:
        undo = move.apply(self)
        self._stack.append(undo)
        self._update_clocks_after_apply(undo)
        if self.tracker is not None:
            self.tracker._att_dirty = True

    def pop_quiet(self) -> None:
        undo = self._stack.pop()

        self.side_to_move = undo.prev_side
        self.last_move = undo.prev_last_move
        self._restore_clocks(undo)
        if self.tracker is not None:
            self.tracker._att_dirty = True

        for p in undo.added:
            self.board.remove_piece(p.pos)
        for p, pos, hm in undo.removed:
            p.pos = pos; p.has_moved = hm; self.board._pieces[pos] = p
        for p, pos, hm in undo.captured:
            p.pos = pos; p.has_moved = hm; self.board._pieces[pos] = p
        for p, pos, hm in undo.changed:
            for k, v in list(self.board._pieces.items()):
                if v is p and k != pos:
                    self.board._pieces.pop(k, None)
                    break
            p.pos = pos; p.has_moved = hm; self.board._pieces[pos] = p
        for p, meta in undo.piece_meta_snapshots:
            p.meta = meta

    def apply_rules(self, color: Color, moves: Iterable[Move]) -> Iterable[Move]:
        out: Iterable[Move] = moves
        for rule in self.rules:
            out = rule.apply(self, color, out)
        return out

    def pseudo_legal_moves(self, color: Color) -> Iterable[Move]:
        for p in self.board.pieces_of(color):
            yield from p.pseudo_legal_moves(self)

    def legal_moves(self, color: Color) -> List[Move]:
        return list(self.apply_rules(color, self.pseudo_legal_moves(color)))

    def is_square_attacked(self, target: int, by_color: Color) -> bool:
        if self.tracker is not None:
            bb = self.tracker.attacked_bb(self, by_color)
            return ((bb >> target) & 1) == 1

        for p in self.board.pieces_of(by_color):
            for a in p.attacks(self):
                if a == target:
                    return True
        return False

    def in_check(self, color: Color) -> bool:
        king = self.board.king_of(color)
        return self.is_square_attacked(king.pos, color.opponent())

# typing-only import
if TYPE_CHECKING:
    from .piece import Piece
