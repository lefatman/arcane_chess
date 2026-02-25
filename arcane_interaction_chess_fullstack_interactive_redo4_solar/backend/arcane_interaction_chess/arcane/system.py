from __future__ import annotations

import random
from typing import List, Optional, Sequence, Tuple

from ..core.game import Listener
from ..core.events import MoveApplied
from ..core.moves import EnPassantMove, PromotionMove
from ..core.types import Color, file_of, rank_of, in_bounds, sq
from ..core.piece import Piece
from ..core.pieces import King
from .definitions import AbilityId, ElementId, ItemId
from .rules import piece_rank
from .state import ArcaneState

class ArcaneResolutionSystem(Listener):
    def __init__(self, game, decisions, rng: random.Random) -> None:
        self.game = game
        self.decisions = decisions
        self.rng = rng

    def on_event(self, game, event: object) -> None:
        if not isinstance(event, MoveApplied):
            return

        # NOTE: event.mover is the *pre-move actor* (e.g. a pawn before promotion).
        mover = event.mover
        move = event.move
        undo = game._stack[-1]

        # The piece that physically represents the capturer *after* the move is applied.
        # - Normal/EP: the same object as `mover`, now sitting on move.to_sq.
        # - Promotion: the pawn is removed; the promoted piece sits on move.to_sq.
        # - Remote capture: the piece does not move.
        post_capturer = mover
        if move.__class__.__name__ != "RemoteCaptureMove":
            maybe = game.board.piece_at(move.to_sq)
            if maybe is not None and maybe.color is mover.color:
                post_capturer = maybe

        # Per-ply semantic effects bucket (JSONified later by API facade)
        undo.extras.setdefault("effects", [])
        effects: List[dict] = undo.extras["effects"]

        # Block Path direction selection (defensive passive on the piece that remains after the action)
        if game.arcane_has_ability(post_capturer, AbilityId.BLOCK_PATH):
            undo.snapshot_piece_meta(post_capturer)
            d = self.decisions.choose_block_path_dir(game, post_capturer)
            post_capturer.meta["block_dir"] = d.value
            effects.append({"type": "block_path", "uid": int(post_capturer.uid), "dir": d.name})

        captured = event.captured
        if captured is None:
            return

        effects.append({
            "type": "capture",
            "capturer_uid": int(mover.uid),
            "captured_uid": int(captured.uid),
            "captured_sq": int(captured.pos),
        })

        # register capture into graveyard (undoable)
        self._snapshot_arcane_undoable(undo)
        game.arcane_state.graveyard[captured.color].append((captured, captured.pos))

        attacker_color = mover.color
        defender_color = captured.color
        attacker_cfg = game.player_config[attacker_color]
        defender_cfg = game.player_config[defender_color]
        attacker_el = attacker_cfg.element
        defender_el = defender_cfg.element

        # Air negates defensive abilities unless defender is Earth
        air_negates_defense = (attacker_el is ElementId.AIR and defender_el is not ElementId.EARTH)

        # --- REDO (defensive, consumable per piece; doubled by Water vs non-Lightning) ---
        if (not air_negates_defense) and game.arcane_has_ability(captured, AbilityId.REDO) and game.arcane_state.redo_charges.get(captured.uid, 0) > 0:
            # Canon update: rewind 4 plies (both players' decisions), except early game where we only rewind 2 plies.
            # (First-turn captures cannot have 4 plies of history.)
            if len(game._stack) >= 2:
                rewind_plies = 4 if len(game._stack) >= 4 else 2

                # The earliest undone ply is the one the defender must change.
                forbidden = game._stack[-rewind_plies].move
                if forbidden is not None:
                    # Spend a charge (monotonic; NOT undone by rewind).
                    game.arcane_state.redo_charges[captured.uid] -= 1

                    # Keep a record of the erased timeline (for UI/animation).
                    undone = [u.move for u in game._stack[-rewind_plies:] if u.move is not None]

                    # Stash redo context on the game so the interactive server/UI can display the correct rewind state.
                    # (This is cleared by the server once the replay move is chosen.)
                    setattr(game, "_pending_redo", {
                        "spent_uid": int(captured.uid),
                        "defender_color": defender_color,
                        "rewind_plies": rewind_plies,
                        "forbidden": forbidden,
                        "undone": undone,
                    })

                    # Transient effect survives the pops and is visible while a decision is pending.
                    game.transient_effects.append({
                        "type": "redo_pending",
                        "spent_uid": int(captured.uid),
                        "forbidden": forbidden,
                        "rewind_plies": rewind_plies,
                        "undone": undone,
                    })

                    # Rewind the timeline first.
                    for _ in range(rewind_plies):
                        game.pop()

                    # Now, from the restored state, the defender replays their turn with a different move.
                    legal = game.legal_moves(defender_color)
                    replay = self.decisions.choose_redo_replay(game, defender_color, forbidden, legal)
                    if replay is not None:
                        # Mark completion for downstream consumers (the server may also upgrade the pending entry).
                        game.transient_effects.append({
                            "type": "redo",
                            "spent_uid": int(captured.uid),
                            "forbidden": forbidden,
                            "replay": replay,
                            "rewind_plies": rewind_plies,
                        })
                        # Clear pending marker (safe in default/non-interactive flow).
                        if hasattr(game, "_pending_redo"):
                            setattr(game, "_pending_redo", None)
                        game.push(replay)
                        return  # do NOT resolve further effects of the original capture

                    # If the decision provider refused to pick (should not happen in interactive flow),
                    # fall back to the first non-forbidden legal move.
                    for m in legal:
                        if (
                            m.__class__ is forbidden.__class__
                            and m.from_sq == forbidden.from_sq
                            and m.to_sq == forbidden.to_sq
                            and getattr(m, "flags", ()) == getattr(forbidden, "flags", ())
                        ):
                            continue
                        game.transient_effects.append({
                            "type": "redo",
                            "spent_uid": int(captured.uid),
                            "forbidden": forbidden,
                            "replay": m,
                            "rewind_plies": rewind_plies,
                        })
                        if hasattr(game, "_pending_redo"):
                            setattr(game, "_pending_redo", None)
                        game.push(m)
                        return

        # decide order for Poisoned Dagger vs offense
        fire_offense_first = (attacker_el is ElementId.FIRE)
        fire_offense_ineffective = (attacker_el is ElementId.FIRE and defender_el is ElementId.WATER)

        # helper to run offenses
        def run_offenses() -> None:
            if fire_offense_ineffective:
                return
            self._resolve_offensive_on_capture(game, undo, mover, captured)

        def run_dagger() -> bool:
            """Returns True if the capturing piece was removed."""
            if defender_cfg.has_item(ItemId.POISONED_DAGGER):
                ar = piece_rank(mover)  # use pre-promotion rank semantics
                dr = piece_rank(captured)
                if ar <= dr:
                    # kill the capturer (post-move physical piece)
                    self._snapshot_arcane_undoable(undo)
                    game.arcane_state.graveyard[post_capturer.color].append((post_capturer, post_capturer.pos))

                    # If the capturer was created this ply (promotion), don't add it to undo.captured,
                    # otherwise it would be incorrectly restored on undo.
                    if post_capturer not in undo.added:
                        undo.captured.append((post_capturer, post_capturer.pos, post_capturer.has_moved))
                    game.board.remove_piece(post_capturer.pos)
                    effects.append({"type": "poisoned_dagger", "victim_uid": int(post_capturer.uid)})
                    return True
            return False

        if fire_offense_first:
            run_offenses()
            run_dagger()
        else:
            killed = run_dagger()
            # if dagger killed the capturer, offensive triggers don't happen
            if not killed and game.board.piece_at(post_capturer.pos) is post_capturer:
                run_offenses()

    def _snapshot_arcane_undoable(self, undo) -> None:
        if "arcane_undoable" not in undo.extras:
            undo.extras["arcane_undoable"] = self.game.arcane_state.snapshot_undoable()

    def _misfire(self, attacker_el: ElementId, defender_el: ElementId) -> bool:
        return attacker_el is ElementId.LIGHTNING and defender_el is ElementId.AIR and (self.rng.random() < 0.5)

    def _resolve_offensive_on_capture(self, game, undo, mover: Piece, captured: Piece) -> None:
        attacker_el = game.player_config[mover.color].element
        defender_el = game.player_config[captured.color].element

        # misfire applies to all offensive abilities when Lightning attacks Air
        misfire_gate = self._misfire(attacker_el, defender_el)

        if misfire_gate:
            # Log only if something offensive was actually slotted on the mover.
            has_any = (
                game.arcane_has_ability(mover, AbilityId.DOUBLE_KILL)
                or game.arcane_has_ability(mover, AbilityId.QUANTUM_KILL)
                or game.arcane_has_ability(mover, AbilityId.NECROMANCER)
            )
            if has_any:
                undo.extras.setdefault("effects", []).append({"type": "lightning_misfire", "uid": int(mover.uid)})

        # DOUBLE KILL
        if game.arcane_has_ability(mover, AbilityId.DOUBLE_KILL) and not misfire_gate:
            capt_sq = captured.pos  # remove neighbor of captured piece square
            cand = []
            cf, cr = file_of(capt_sq), rank_of(capt_sq)
            for df in (-1, 0, 1):
                for dr in (-1, 0, 1):
                    if df == 0 and dr == 0:
                        continue
                    f, r = cf + df, cr + dr
                    if not in_bounds(f, r):
                        continue
                    p = game.board.piece_at(sq(f, r))
                    if p is None or p.color is mover.color:
                        continue
                    if piece_rank(p) <= piece_rank(mover):
                        cand.append(p)
            chosen = self.decisions.choose_double_kill_target(game, mover, cand)
            if chosen is not None:
                self._snapshot_arcane_undoable(undo)
                game.arcane_state.graveyard[chosen.color].append((chosen, chosen.pos))
                undo.captured.append((chosen, chosen.pos, chosen.has_moved))
                game.board.remove_piece(chosen.pos)
                undo.extras.setdefault("effects", []).append({"type": "double_kill", "victim_uid": int(chosen.uid)})

        # QUANTUM KILL
        if game.arcane_has_ability(mover, AbilityId.QUANTUM_KILL) and not misfire_gate:
            elig = []
            for p in game.board.pieces_of(captured.color):
                if piece_rank(p) <= piece_rank(mover):
                    elig.append(p)
            if elig:
                victim = self.rng.choice(elig)
                self._snapshot_arcane_undoable(undo)
                game.arcane_state.graveyard[victim.color].append((victim, victim.pos))
                undo.captured.append((victim, victim.pos, victim.has_moved))
                game.board.remove_piece(victim.pos)
                undo.extras.setdefault("effects", []).append({"type": "quantum_kill", "victim_uid": int(victim.uid)})

        # NECROMANCER
        if game.arcane_has_ability(mover, AbilityId.NECROMANCER) and not misfire_gate:
            if piece_rank(captured) > piece_rank(mover):
                pool = game.arcane_state.necro_pool[mover.color]
                if pool > 0:
                    # pick an eligible captured friendly piece whose capture square is empty; exclude king
                    options: List[Tuple[Piece, int]] = []
                    for obj, cap_sq in game.arcane_state.graveyard[mover.color]:
                        p = obj  # type: ignore[assignment]
                        if isinstance(p, King):
                            continue
                        if game.board.piece_at(cap_sq) is None:
                            options.append((p, cap_sq))
                    chosen = self.decisions.choose_necromancer_resurrect(game, options)
                    if chosen is not None:
                        p, cap_sq = chosen
                        self._snapshot_arcane_undoable(undo)
                        # remove from graveyard
                        game.arcane_state.graveyard[mover.color] = [(o, s) for (o, s) in game.arcane_state.graveyard[mover.color] if o is not p]
                        game.arcane_state.necro_pool[mover.color] -= 1
                        # resurrect onto capture square
                        p.pos = cap_sq
                        game.board.add_piece(p)
                        undo.added.append(p)
                        undo.extras.setdefault("effects", []).append({"type": "necromancer", "resurrect_uid": int(p.uid), "to_sq": int(cap_sq)})
