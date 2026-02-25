import importlib.util
import sys
import unittest
from pathlib import Path


SENTINEL = object()


def _load_frontend_server_module():
    root = Path(__file__).resolve().parents[2]
    mod_path = root / "frontend" / "server.py"
    spec = importlib.util.spec_from_file_location("frontend_server_effect_guards", mod_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load frontend server module")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("frontend_server_effect_guards", module)
    spec.loader.exec_module(module)
    return module


class TestMalformedEffectPayloadGuards(unittest.TestCase):
    def test_gather_effects_uses_deterministic_fallback_for_bad_undone_payload(self):
        server_module = _load_frontend_server_module()
        engine = server_module.ServerEngine.standard_demo_game()
        game = engine.game

        original_move_to_uci = server_module.move_to_uci
        original_move_to_dict = server_module.move_to_dict

        def bad_move_to_uci(move):
            if move is SENTINEL:
                raise TypeError("bad move payload")
            return original_move_to_uci(move)

        def bad_move_to_dict(move):
            if move is SENTINEL:
                raise TypeError("bad move payload")
            return original_move_to_dict(move)

        server_module.move_to_uci = bad_move_to_uci
        server_module.move_to_dict = bad_move_to_dict
        try:
            game.transient_effects = [{"type": "redo", "undone": [SENTINEL]}]
            effects = engine._gather_effects()
        finally:
            server_module.move_to_uci = original_move_to_uci
            server_module.move_to_dict = original_move_to_dict

        self.assertEqual(len(effects), 1)
        self.assertEqual(effects[0].get("undone_uci"), [])
        self.assertEqual(effects[0].get("undone"), [])
        self.assertEqual(effects[0].get("undone_error"), "invalid_effect_undone_payload")

    def test_redo_prompt_uses_deterministic_fallback_for_bad_pending_undone(self):
        server_module = _load_frontend_server_module()
        engine = server_module.ServerEngine.standard_demo_game()
        game = engine.game
        legal = game.legal_moves(game.side_to_move)

        self.assertGreater(len(legal), 1)
        forbidden = legal[0]
        game._pending_redo = {"rewind_plies": 1, "spent_uid": 42, "undone": [SENTINEL]}

        original_move_to_uci = server_module.move_to_uci

        def bad_move_to_uci(move):
            if move is SENTINEL:
                raise TypeError("bad move payload")
            return original_move_to_uci(move)

        server_module.move_to_uci = bad_move_to_uci
        try:
            with self.assertRaises(server_module.NeedDecision) as raised:
                engine.decisions.choose_redo_replay(game, game.side_to_move, forbidden, legal)
        finally:
            server_module.move_to_uci = original_move_to_uci

        payload = raised.exception.payload
        self.assertEqual(payload["kind"], "redo_replay")
        self.assertEqual(payload["context"].get("undone_uci"), [])
        self.assertEqual(payload["context"].get("undone_uci_error"), "invalid_undone_payload")


if __name__ == "__main__":
    unittest.main()
