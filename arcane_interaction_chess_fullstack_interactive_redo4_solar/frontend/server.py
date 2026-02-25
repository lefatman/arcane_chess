#!/usr/bin/env python3
"""Arcane Interaction Chess: local dev server (stdlib only).

Serves:
- Static frontend (HTML/CSS/JS)
- JSON API wrapping the backend engine, with interactive "decision" prompts
  for arcane abilities (Block Path / Double Kill / Necromancer / Redo).

This file lives entirely inside the frontend/ directory so the backend codebase
remains untouched.

Run from repo root:
  python frontend/server.py

Then open:
  http://127.0.0.1:8000/
"""

from __future__ import annotations

import argparse
from dataclasses import fields, is_dataclass
import json
import os
import socket
import sys
import threading
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from pathlib import Path
from typing import Any, Dict, Optional, List
import secrets


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

# Ensure backend package import works
sys.path.insert(0, str(BACKEND_ROOT))

from arcane_interaction_chess.api import snapshot, dict_to_move, move_to_dict, move_to_uci
from arcane_interaction_chess.api.facade import diff as snapshot_diff
from arcane_interaction_chess.san import to_san
from arcane_interaction_chess.arcane.game import ArcaneGame
from arcane_interaction_chess.arcane.loadout import PlayerConfig, AbilitySlot
from arcane_interaction_chess.arcane.definitions import ElementId, ItemId, AbilityId, ITEM_SLOT_COST, ABILITY_DEFS, CardinalDir
from arcane_interaction_chess.arcane.decisions import DecisionProvider
from arcane_interaction_chess.core.types import Color


class PayloadTooLargeError(ValueError):
    pass


class RequestReadTimeoutError(ValueError):
    pass


def _json_read(
    rfile,
    *,
    content_length: Optional[int],
    max_bytes: int = 1_000_000,
    socket_obj: Optional[socket.socket] = None,
    read_timeout_s: Optional[float] = None,
) -> Dict[str, Any]:
    if content_length is None:
        raise ValueError("Missing Content-Length")

    max_allowed = int(os.environ.get("ARCANE_HTTP_MAX", str(max_bytes)))
    if content_length < 0:
        raise ValueError("Invalid Content-Length")
    if content_length > max_allowed:
        raise PayloadTooLargeError("Payload too large")

    prev_timeout = None
    if socket_obj is not None and read_timeout_s is not None:
        prev_timeout = socket_obj.gettimeout()
        socket_obj.settimeout(read_timeout_s)

    try:
        raw = rfile.read(content_length) if content_length > 0 else b""
    except TimeoutError as e:
        raise RequestReadTimeoutError("Request body read timed out") from e
    except socket.timeout as e:
        raise RequestReadTimeoutError("Request body read timed out") from e
    finally:
        if socket_obj is not None and read_timeout_s is not None:
            socket_obj.settimeout(prev_timeout)

    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception as e:
        raise ValueError(f"Invalid JSON: {e}")


def _json_write(handler: SimpleHTTPRequestHandler, status: int, payload: Dict[str, Any]) -> None:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(data)))
    # Same-origin by default; allow localhost tools to talk to it.
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(data)


def _bad(handler: SimpleHTTPRequestHandler, msg: str, status: int = 400) -> None:
    _json_write(handler, status, {"ok": False, "error": msg})


def _defs() -> Dict[str, Any]:
    elements = [
        {"id": int(ElementId.WATER), "name": "Water"},
        {"id": int(ElementId.FIRE), "name": "Fire"},
        {"id": int(ElementId.EARTH), "name": "Earth"},
        {"id": int(ElementId.AIR), "name": "Air/Wind"},
        {"id": int(ElementId.LIGHTNING), "name": "Lightning"},
    ]

    items = []
    name_map = {
        ItemId.MULTITASKERS_SCHEDULE: "Multitasker’s Schedule",
        ItemId.POISONED_DAGGER: "Poisoned Dagger",
        ItemId.DUAL_ADEPTS_GLOVES: "Dual Adept’s Gloves",
        ItemId.TRIPLE_ADEPTS_GLOVES: "Triple Adept’s Gloves",
        ItemId.HEADMASTER_RING: "Headmaster Ring",
        ItemId.POT_OF_HUNGER: "Pot of Hunger",
        ItemId.SOLAR_NECKLACE: "Solar Necklace",
    }
    for it, cost in ITEM_SLOT_COST.items():
        items.append({"id": int(it), "name": name_map.get(it, it.name), "slot_cost": int(cost)})
    items.sort(key=lambda x: x["id"])

    abilities = []
    for aid, adef in ABILITY_DEFS.items():
        abilities.append(
            {
                "id": int(aid),
                "name": adef.name,
                "scope": adef.scope.value,
                "category": adef.category.value,
                "consumable": bool(adef.consumable),
            }
        )
    abilities.sort(key=lambda x: x["id"])

    return {"elements": elements, "items": items, "abilities": abilities}


def _parse_config(obj: Dict[str, Any]) -> PlayerConfig:
    element_id = int(obj.get("element_id", int(ElementId.EARTH)))
    element = ElementId(element_id)

    items = [ItemId(int(x)) for x in (obj.get("items") or [])]

    abil_slots = []
    for s in (obj.get("abilities") or []):
        abil = AbilityId(int(s["ability"]))
        ptype = s.get("piece_type")
        if ptype is not None:
            ptype = str(ptype)
        abil_slots.append(AbilitySlot(ability=abil, piece_type=ptype))

    cfg = PlayerConfig(element=element, items=items, abilities=abil_slots)
    cfg.validate()
    return cfg


class NeedDecision(Exception):
    def __init__(self, payload: Dict[str, Any]) -> None:
        super().__init__(payload.get("kind", "decision"))
        self.payload = payload


class InteractiveDecisions:
    """DecisionProvider that can pause the engine and ask the UI."""

    def __init__(self) -> None:
        self.choices: Dict[str, Any] = {}

    def clear(self) -> None:
        self.choices.clear()

    def _need(self, kind: str, prompt: str, options: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        raise NeedDecision({"kind": kind, "prompt": prompt, "options": options, "context": context})

    def choose_block_path_dir(self, game, mover):
        k = "block_path_dir"
        if k in self.choices:
            return CardinalDir[self.choices[k]]
        opts = [{"id": d.name, "label": d.name.title()} for d in CardinalDir]
        ctx = {"mover_uid": int(mover.uid), "mover_sq": int(mover.pos)}
        self._need(k, "Choose Block Path direction", opts, ctx)

    def choose_double_kill_target(self, game, capturer, candidates):
        k = "double_kill_target"
        if not candidates:
            return None
        if k in self.choices:
            choice = self.choices[k]
            if choice == "skip":
                return None
            uid = int(choice)
            for p in candidates:
                if int(p.uid) == uid:
                    return p
            return None
        opts = [
            {
                "id": str(int(p.uid)),
                "label": f"{type(p).__name__} @ {game.board.alg(p.pos)} (uid {int(p.uid)})",
                "sq": int(p.pos),
                "uid": int(p.uid),
                "type": type(p).__name__,
            }
            for p in candidates
        ]
        opts.append({"id": "skip", "label": "Skip"})
        ctx = {"capturer_uid": int(capturer.uid)}
        self._need(k, "Choose Double Kill target", opts, ctx)

    def choose_necromancer_resurrect(self, game, candidates):
        k = "necromancer_resurrect"
        if not candidates:
            return None
        if k in self.choices:
            choice = self.choices[k]
            if choice == "skip":
                return None
            uid = int(choice)
            for (p, cap_sq) in candidates:
                if int(p.uid) == uid:
                    return (p, int(cap_sq))
            return None
        opts = []
        for (p, cap_sq) in candidates:
            opts.append(
                {
                    "id": str(int(p.uid)),
                    "label": f"{type(p).__name__} -> {game.board.alg(int(cap_sq))} (uid {int(p.uid)})",
                    "uid": int(p.uid),
                    "to_sq": int(cap_sq),
                    "to_alg": game.board.alg(int(cap_sq)),
                    "type": type(p).__name__,
                }
            )
        opts.append({"id": "skip", "label": "Skip"})
        self._need(k, "Choose Necromancer resurrect", opts, {})

    def choose_redo_replay(self, game, defender_color, forbidden, legal):
        k = "redo_replay"
        # If no alternative exists, no redo.
        has_alt = False
        for m in legal:
            if (
                m.__class__ is forbidden.__class__
                and m.from_sq == forbidden.from_sq
                and m.to_sq == forbidden.to_sq
                and getattr(m, "flags", ()) == getattr(forbidden, "flags", ())
            ):
                continue
            has_alt = True
            break
        if not has_alt:
            return None

        if k in self.choices:
            uci = str(self.choices[k])
            for m in legal:
                if move_to_uci(m) == uci:
                    if (
                        m.__class__ is forbidden.__class__
                        and m.from_sq == forbidden.from_sq
                        and m.to_sq == forbidden.to_sq
                        and getattr(m, "flags", ()) == getattr(forbidden, "flags", ())
                    ):
                        return None
                    return m
            return None

        opts = []
        for m in legal:
            if (
                m.__class__ is forbidden.__class__
                and m.from_sq == forbidden.from_sq
                and m.to_sq == forbidden.to_sq
                and getattr(m, "flags", ()) == getattr(forbidden, "flags", ())
            ):
                continue
            opts.append({"id": move_to_uci(m), "label": move_to_uci(m), "move": move_to_dict(m)})
        ctx = {
            "side": "WHITE" if defender_color is Color.WHITE else "BLACK",
            "forbidden": move_to_dict(forbidden),
            "forbidden_uci": move_to_uci(forbidden),
        }
        pr = getattr(game, "_pending_redo", None)
        if isinstance(pr, dict):
            if pr.get("rewind_plies") is not None:
                ctx["rewind_plies"] = int(pr.get("rewind_plies"))
            if pr.get("spent_uid") is not None:
                ctx["spent_uid"] = int(pr.get("spent_uid"))
            undone = pr.get("undone")
            if isinstance(undone, list) and undone:
                try:
                    ctx["undone_uci"] = [move_to_uci(m) for m in undone]
                except Exception:
                    pass
        self._need(k, "Redo triggered: choose an alternate replay move", opts, ctx)


class ServerEngine:
    def __init__(self, white: PlayerConfig, black: PlayerConfig, rng_seed: int = 1337) -> None:
        self.decisions: DecisionProvider = InteractiveDecisions()
        self.game = ArcaneGame(white=white, black=black, decisions=self.decisions, rng_seed=rng_seed)
        self.game.setup_standard()
        self.game.attach_tracker()

    @classmethod
    def standard_demo_game(cls) -> "ServerEngine":
        w = PlayerConfig(element=ElementId.EARTH, items=[], abilities=[])
        b = PlayerConfig(element=ElementId.EARTH, items=[], abilities=[])
        return cls(w, b, rng_seed=1337)

    def state(self) -> Dict[str, Any]:
        return snapshot(self.game)

    def legal_moves(self) -> List[Dict[str, Any]]:
        return [move_to_dict(m) for m in self.game.legal_moves(self.game.side_to_move)]

    def _notation_for_last_move(self) -> Optional[Dict[str, Any]]:
        lm = self.game.last_move
        if lm is None or not getattr(self.game, "_stack", None):
            return None
        self.game.pop_quiet()
        try:
            return {"uci": move_to_uci(lm), "san": to_san(self.game, lm), "move": move_to_dict(lm)}
        finally:
            self.game.push_quiet(lm)

    def _gather_effects(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for e in getattr(self.game, "transient_effects", []) or []:
            ee = dict(e)
            if "forbidden" in ee and ee["forbidden"] is not None:
                ee["forbidden"] = move_to_dict(ee["forbidden"])
            if "replay" in ee and ee["replay"] is not None:
                ee["replay"] = move_to_dict(ee["replay"])
            if "undone" in ee and isinstance(ee["undone"], list):
                try:
                    ee["undone_uci"] = [move_to_uci(m) for m in ee["undone"] if m is not None]
                    ee["undone"] = [move_to_dict(m) for m in ee["undone"] if m is not None]
                except Exception:
                    pass
            out.append(ee)
        if getattr(self.game, "_stack", None):
            last_undo = self.game._stack[-1]
            for e in last_undo.extras.get("effects", []) or []:
                out.append(dict(e))
        return out

    def apply(self, move_dict: Dict[str, Any]) -> Dict[str, Any]:
        pre_len = len(getattr(self.game, "_stack", []))
        before = snapshot(self.game)
        requested = dict_to_move(move_dict)

        legal = self.game.legal_moves(self.game.side_to_move)
        m = None
        if is_dataclass(requested):
            for candidate in legal:
                if candidate.__class__ is not requested.__class__:
                    continue
                if not is_dataclass(candidate):
                    continue
                matches = True
                for f in fields(candidate):
                    if getattr(candidate, f.name) != getattr(requested, f.name):
                        matches = False
                        break
                if matches:
                    m = candidate
                    break
        if m is None:
            raise ValueError("Illegal move")

        applied_notation = {"uci": move_to_uci(m), "san": to_san(self.game, m)}
        try:
            self.game.push(m)
        except NeedDecision:
            while len(self.game._stack) > pre_len:
                self.game.pop()
            raise
        after = snapshot(self.game)
        d = snapshot_diff(before, after)
        meta = {
            "applied": move_to_dict(m),
            "applied_notation": applied_notation,
            "result_last_move": after.get("last_move"),
            "result_last_notation": self._notation_for_last_move(),
            "effects": self._gather_effects(),
            "check": after.get("check"),
            "checkmate": after.get("checkmate"),
        }
        return {"before": before, "after": after, "diff": d, "meta": meta}

    def undo(self) -> Dict[str, Any]:
        if not self.game._stack:
            raise ValueError("No moves to undo")
        before = snapshot(self.game)
        undone_move = self.game.last_move
        undone_meta = None
        if undone_move is not None and getattr(self.game, "_stack", None):
            last_undo = self.game._stack[-1]
            undone_meta = {"move": move_to_dict(undone_move), "uci": move_to_uci(undone_move)}
            self.game.pop_quiet()
            try:
                undone_meta["san"] = to_san(self.game, undone_move)
            finally:
                self.game.push_quiet(undone_move)
            undone_meta["effects"] = [dict(e) for e in last_undo.extras.get("effects", []) or []]
        self.game.pop()
        after = snapshot(self.game)
        return {"before": before, "after": after, "diff": snapshot_diff(before, after), "meta": {"undone": undone_meta}}


class _State:
    engine: ServerEngine
    pending: Optional[Dict[str, Any]]
    pending_move: Optional[Dict[str, Any]]

    def __init__(self) -> None:
        self.engine = ServerEngine.standard_demo_game()
        self.pending = None
        self.pending_move = None

STATE = _State()
STATE_LOCK = threading.RLock()


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class Handler(SimpleHTTPRequestHandler):
    # Serve files from frontend/ as the web root
    def translate_path(self, path: str) -> str:
        # static root = this directory
        root = Path(__file__).resolve().parent
        # strip query
        path = path.split("?", 1)[0].split("#", 1)[0]
        rel = path.lstrip("/")
        target = (root / rel).resolve()
        if root not in target.parents and target != root:
            return str(root / "index.html")
        if target.is_dir():
            target = target / "index.html"
        return str(target)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        if self.path.startswith("/api/"):
            self._handle_api_get()
            return
        return super().do_GET()

    def do_POST(self) -> None:
        if self.path.startswith("/api/"):
            self._handle_api_post()
            return
        self.send_error(HTTPStatus.NOT_FOUND, "No such endpoint")

    def _handle_api_get(self) -> None:
        try:
            if self.path.startswith("/api/defs"):
                _json_write(self, 200, {"ok": True, "defs": _defs()})
                return
            if self.path.startswith("/api/state"):
                with STATE_LOCK:
                    state = STATE.engine.state()
                _json_write(self, 200, {"ok": True, "state": state})
                return
            if self.path.startswith("/api/legal"):
                with STATE_LOCK:
                    moves = STATE.engine.legal_moves()
                _json_write(self, 200, {"ok": True, "moves": moves})
                return
            if self.path.startswith("/api/pending"):
                with STATE_LOCK:
                    pending = STATE.pending
                _json_write(self, 200, {"ok": True, "pending": pending})
                return
        except Exception as e:
            _bad(self, str(e), 500)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "No such endpoint")

    def _handle_api_post(self) -> None:
        try:
            length_header = self.headers.get("Content-Length")
            length = int(length_header) if length_header is not None else None
        except (TypeError, ValueError):
            _bad(self, "Invalid Content-Length", 400)
            return

        try:
            body = _json_read(
                self.rfile,
                content_length=length,
                socket_obj=self.connection,
                read_timeout_s=float(os.environ.get("ARCANE_HTTP_READ_TIMEOUT", "5.0")),
            )
        except PayloadTooLargeError as e:
            _bad(self, str(e), 413)
            return
        except RequestReadTimeoutError as e:
            _bad(self, str(e), 408)
            return
        except ValueError as e:
            msg = str(e)
            if msg == "Missing Content-Length":
                _bad(self, msg, 411)
            else:
                _bad(self, msg, 400)
            return
        except Exception as e:
            _bad(self, f"Invalid JSON: {e}")
            return

        try:
            if self.path.startswith("/api/reset"):
                with STATE_LOCK:
                    STATE.engine = ServerEngine.standard_demo_game()
                    STATE.pending = None
                    STATE.pending_move = None
                    state = STATE.engine.state()
                _json_write(self, 200, {"ok": True, "state": state})
                return

            if self.path.startswith("/api/newgame"):
                white = _parse_config(body.get("white") or {})
                black = _parse_config(body.get("black") or {})
                seed = int(body.get("rng_seed", 1337))
                with STATE_LOCK:
                    STATE.engine = ServerEngine(white=white, black=black, rng_seed=seed)
                    STATE.pending = None
                    STATE.pending_move = None
                    state = STATE.engine.state()
                _json_write(self, 200, {"ok": True, "state": state})
                return

            if self.path.startswith("/api/apply"):
                mv = body.get("move")
                if not isinstance(mv, dict):
                    _bad(self, "Missing move dict")
                    return
                with STATE_LOCK:
                    if STATE.pending is not None:
                        _bad(self, "Decision pending: resolve /api/decide or /api/cancel")
                        return
                    STATE.engine.decisions.clear()
                    try:
                        res = STATE.engine.apply(mv)
                    except ValueError as e:
                        _bad(self, str(e), 400)
                        return
                    except NeedDecision as nd:
                        pid = secrets.token_urlsafe(10)
                        kind = str(nd.payload.get("kind"))
                        STATE.pending_move = None if kind == "redo_replay" else mv
                        STATE.pending = {"id": pid, **nd.payload}
                        pending = STATE.pending
                        state = STATE.engine.state()
                    else:
                        _json_write(self, 200, {"ok": True, "result": res})
                        return
                _json_write(self, 200, {"ok": True, "pending": pending, "state": state})
                return

            if self.path.startswith("/api/decide"):
                pid = body.get("id")
                choice = body.get("choice")
                with STATE_LOCK:
                    if STATE.pending is None:
                        _bad(self, "No pending decision")
                        return
                    if str(pid) != str(STATE.pending.get("id")):
                        _bad(self, "Pending decision id mismatch")
                        return

                    kind = str(STATE.pending.get("kind"))
                    STATE.engine.decisions.choices[kind] = choice
                    try:
                        if STATE.pending_move is None and kind == "redo_replay":
                            g = STATE.engine.game
                            chosen = None
                            for m in g.legal_moves(g.side_to_move):
                                if move_to_uci(m) == str(choice):
                                    chosen = m
                                    break
                            if chosen is None:
                                _bad(self, "Invalid redo replay choice")
                                return

                            pr = getattr(g, "_pending_redo", None)
                            if isinstance(pr, dict):
                                for e in reversed(getattr(g, "transient_effects", []) or []):
                                    if e.get("type") == "redo_pending" and int(e.get("spent_uid", -1)) == int(pr.get("spent_uid", -2)):
                                        e["type"] = "redo"
                                        e["replay"] = chosen
                                        break

                            mv_dict = move_to_dict(chosen)
                            res = STATE.engine.apply(mv_dict)
                            STATE.pending = None
                            STATE.pending_move = None
                            if hasattr(g, "_pending_redo"):
                                setattr(g, "_pending_redo", None)
                            _json_write(self, 200, {"ok": True, "result": res})
                            return

                        if STATE.pending_move is None:
                            _bad(self, "No pending move to apply")
                            return
                        res = STATE.engine.apply(STATE.pending_move)
                        STATE.pending = None
                        STATE.pending_move = None
                        _json_write(self, 200, {"ok": True, "result": res})
                        return
                    except ValueError as e:
                        _bad(self, str(e), 400)
                        return
                    except NeedDecision as nd:
                        STATE.pending.update({k: v for k, v in nd.payload.items() if k != "kind"})
                        STATE.pending["kind"] = nd.payload.get("kind")
                        if STATE.pending_move is None and kind == "redo_replay":
                            g = STATE.engine.game
                            for m in g.legal_moves(g.side_to_move):
                                if move_to_uci(m) == str(choice):
                                    STATE.pending_move = move_to_dict(m)
                                    break
                        pending = STATE.pending
                        state = STATE.engine.state()
                _json_write(self, 200, {"ok": True, "pending": pending, "state": state})
                return

            if self.path.startswith("/api/cancel"):
                with STATE_LOCK:
                    STATE.pending = None
                    STATE.pending_move = None
                    STATE.engine.decisions.clear()
                    state = STATE.engine.state()
                _json_write(self, 200, {"ok": True, "state": state})
                return

            if self.path.startswith("/api/undo"):
                with STATE_LOCK:
                    STATE.pending = None
                    STATE.pending_move = None
                    STATE.engine.decisions.clear()
                    try:
                        res = STATE.engine.undo()
                    except ValueError as e:
                        _bad(self, str(e), 400)
                        return
                _json_write(self, 200, {"ok": True, "result": res})
                return

            if self.path.startswith("/api/solar_topup"):
                kind = str(body.get("kind", "redo")).lower()
                uid = body.get("uid")
                with STATE_LOCK:
                    if STATE.pending is not None:
                        _bad(self, "Decision pending: resolve before using Solar Necklace")
                        return

                    g = STATE.engine.game
                    st = g.arcane_state
                    c = g.side_to_move
                    cfg = g.player_config[c]

                    if not cfg.has_item(ItemId.SOLAR_NECKLACE):
                        _bad(self, "Solar Necklace not equipped")
                        return
                    if st.solar_uses[c] <= 0:
                        _bad(self, "No Solar uses remaining")
                        return

                    before = snapshot(g)
                    try:
                        g.transient_effects.clear()
                    except Exception:
                        pass

                    if kind == "necro":
                        if int(st.necro_max[c]) <= 0:
                            _bad(self, "Necromancer is not equipped for this side")
                            return
                        if int(st.necro_pool[c]) >= int(st.necro_max[c]):
                            _bad(self, "Necromancer pool already full")
                            return
                        st.necro_bonus[c] = int(st.necro_bonus.get(c, 0)) + 1
                        st.necro_max[c] = int(st.necro_max[c]) + 1
                        st.necro_pool[c] = int(st.necro_pool[c]) + 1
                        g.transient_effects.append({"type": "solar_topup", "kind": "necro", "side": "WHITE" if c is Color.WHITE else "BLACK"})
                    else:
                        if uid is None:
                            _bad(self, "uid required for redo topup")
                            return
                        uid = int(uid)
                        p = g.board._pieces.get(next((sq for sq, pp in g.board._pieces.items() if int(pp.uid) == uid), -1))
                        if p is None:
                            for pp in g.board._pieces.values():
                                if int(pp.uid) == uid:
                                    p = pp
                                    break
                        if p is None or p.color is not c:
                            _bad(self, "Invalid target piece")
                            return
                        if st.redo_max.get(uid, 0) <= 0:
                            _bad(self, "Target piece has no Redo charges")
                            return
                        if st.redo_charges.get(uid, 0) >= st.redo_max.get(uid, 0):
                            _bad(self, "Redo charges already full")
                            return
                        st.redo_charges[uid] = min(int(st.redo_charges.get(uid, 0)) + 1, int(st.redo_max.get(uid, 0)))
                        g.transient_effects.append({"type": "solar_topup", "kind": "redo", "side": "WHITE" if c is Color.WHITE else "BLACK", "uid": uid})

                    st.solar_uses[c] = int(st.solar_uses[c]) - 1

                    after = snapshot(g)
                    d = snapshot_diff(before, after)
                    meta = {
                        "applied": None,
                        "applied_notation": None,
                        "result_last_move": after.get("last_move"),
                        "result_last_notation": STATE.engine._notation_for_last_move(),
                        "effects": STATE.engine._gather_effects(),
                        "check": after.get("check"),
                        "checkmate": after.get("checkmate"),
                    }
                _json_write(self, 200, {"ok": True, "result": {"before": before, "after": after, "diff": d, "meta": meta}})
                return

        except Exception as e:
            _bad(self, str(e), 500)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "No such endpoint")



def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()

    os.chdir(Path(__file__).resolve().parent)

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Arcane Chess frontend at http://{args.host}:{args.port}/")
    print("API: /api/state /api/legal /api/apply /api/decide /api/pending /api/cancel /api/undo /api/newgame /api/defs")
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
