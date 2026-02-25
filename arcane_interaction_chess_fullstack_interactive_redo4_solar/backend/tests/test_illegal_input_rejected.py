import importlib.util
import json
import os
import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from arcane_interaction_chess.core import Game, setup_standard
from arcane_interaction_chess.core.moves import NormalMove
from arcane_interaction_chess.core.types import FILES, sq


def _sq(alg: str) -> int:
    file_idx = FILES.index(alg[0])
    rank_idx = int(alg[1]) - 1
    return sq(file_idx, rank_idx)


def _load_frontend_server_module():
    root = Path(__file__).resolve().parents[2]
    mod_path = root / "frontend" / "server.py"
    spec = importlib.util.spec_from_file_location("frontend_server", mod_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load frontend server module")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("frontend_server", module)
    spec.loader.exec_module(module)
    return module


class TestIllegalInputRejected(unittest.TestCase):
    def _post_json(self, url: str, payload: dict):
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = json.loads(exc.read().decode("utf-8"))
            return int(exc.code), body

    def _get_json(self, url: str):
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8")
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                payload = {"raw": body}
            return int(exc.code), payload

    def _start_server(self, server_module):
        server_module.STATE.engine = server_module.ServerEngine.standard_demo_game()
        server_module.STATE.pending = None
        server_module.STATE.pending_move = None

        httpd = server_module.ThreadingHTTPServer(("127.0.0.1", 0), server_module.Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        return httpd, thread

    def test_push_rejects_opposite_color_piece(self):
        g = Game()
        setup_standard(g)
        with self.assertRaisesRegex(ValueError, "Wrong side to move"):
            g.push(NormalMove(_sq("e7"), _sq("e6")))

    def test_push_checked_rejects_illegal_knight_and_king_moves(self):
        g = Game()
        setup_standard(g)
        with self.assertRaisesRegex(ValueError, "Illegal move"):
            g.push_checked(NormalMove(_sq("b1"), _sq("b4")))
        with self.assertRaisesRegex(ValueError, "Illegal move"):
            g.push_checked(NormalMove(_sq("e1"), _sq("e3")))

    def test_server_engine_rejects_malformed_and_mismatched_move_fields(self):
        server_module = _load_frontend_server_module()
        engine = server_module.ServerEngine.standard_demo_game()


        with self.assertRaisesRegex(ValueError, "Illegal move"):
            engine.apply({"kind": "normal", "from_alg": "e7", "to_alg": "e6"})

        with self.assertRaisesRegex(ValueError, "Illegal move"):
            engine.apply({"kind": "normal", "from_alg": "b1", "to_alg": "b4"})

        with self.assertRaisesRegex(ValueError, "Illegal move"):
            engine.apply({"kind": "promotion", "from_alg": "e2", "to_alg": "e4", "promote_to": "Queen"})

        with self.assertRaisesRegex(ValueError, "Illegal move"):
            engine.apply({"kind": "normal", "from_alg": "e2", "to_alg": "e4", "flags": ["bogus"]})

    def test_server_engine_undo_empty_stack_raises_value_error(self):
        server_module = _load_frontend_server_module()
        engine = server_module.ServerEngine.standard_demo_game()

        with self.assertRaisesRegex(ValueError, "No moves to undo"):
            engine.undo()

    def test_server_engine_undo_reverts_last_move(self):
        server_module = _load_frontend_server_module()
        engine = server_module.ServerEngine.standard_demo_game()

        move = engine.legal_moves()[0]
        applied = engine.apply(move)
        self.assertEqual(applied["meta"]["applied"]["from_alg"], move["from_alg"])
        self.assertEqual(applied["meta"]["applied"]["to_alg"], move["to_alg"])

        undone = engine.undo()
        self.assertIsNone(undone["after"]["last_move"])
        self.assertEqual(undone["meta"]["undone"]["move"]["from_alg"], move["from_alg"])
        self.assertEqual(undone["meta"]["undone"]["move"]["to_alg"], move["to_alg"])

    def test_api_apply_returns_400_for_illegal_input(self):
        server_module = _load_frontend_server_module()
        httpd, thread = self._start_server(server_module)

        try:
            url = f"http://127.0.0.1:{httpd.server_port}/api/apply"
            payload = json.dumps({"move": {"kind": "normal", "from_alg": "e7", "to_alg": "e6"}}).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as exc:
                urllib.request.urlopen(req)
            self.assertEqual(exc.exception.code, 400)
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=2)

    def test_api_undo_empty_returns_400_with_error_payload(self):
        server_module = _load_frontend_server_module()
        httpd, thread = self._start_server(server_module)

        try:
            status, body = self._post_json(f"http://127.0.0.1:{httpd.server_port}/api/undo", {})
            self.assertEqual(status, 400)
            self.assertEqual(body.get("ok"), False)
            self.assertIsInstance(body.get("error"), str)
            self.assertEqual(body.get("error"), "No moves to undo")
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=2)

    def test_api_undo_after_apply_returns_200_with_result(self):
        server_module = _load_frontend_server_module()
        httpd, thread = self._start_server(server_module)

        try:
            base = f"http://127.0.0.1:{httpd.server_port}"
            legal_status, legal_body = self._get_json(f"{base}/api/legal")
            self.assertEqual(legal_status, 200)
            self.assertTrue(legal_body.get("ok"))
            move = legal_body["moves"][0]

            apply_status, apply_body = self._post_json(
                f"{base}/api/apply",
                {"move": move},
            )
            self.assertEqual(apply_status, 200)
            self.assertTrue(apply_body.get("ok"))

            status, body = self._post_json(f"{base}/api/undo", {})
            self.assertEqual(status, 200)
            self.assertTrue(body.get("ok"))
            self.assertIn("result", body)
            self.assertEqual(body["result"]["meta"]["undone"]["move"]["from_alg"], move["from_alg"])
            self.assertEqual(body["result"]["meta"]["undone"]["move"]["to_alg"], move["to_alg"])
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=2)

    def test_api_reset_rejects_oversized_payload_with_413(self):
        server_module = _load_frontend_server_module()
        old_limit = os.environ.get("ARCANE_HTTP_MAX")
        os.environ["ARCANE_HTTP_MAX"] = "16"
        httpd, thread = self._start_server(server_module)

        try:
            url = f"http://127.0.0.1:{httpd.server_port}/api/reset"
            payload = json.dumps({"pad": "x" * 128}).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as exc:
                urllib.request.urlopen(req)
            self.assertEqual(exc.exception.code, 413)
        finally:
            if old_limit is None:
                os.environ.pop("ARCANE_HTTP_MAX", None)
            else:
                os.environ["ARCANE_HTTP_MAX"] = old_limit
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=2)

    def test_api_reset_rejects_invalid_json_with_400(self):
        server_module = _load_frontend_server_module()
        httpd, thread = self._start_server(server_module)

        try:
            url = f"http://127.0.0.1:{httpd.server_port}/api/reset"
            payload = b'{"broken": '
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as exc:
                urllib.request.urlopen(req)
            self.assertEqual(exc.exception.code, 400)
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=2)

    def test_api_reset_accepts_normal_payload(self):
        server_module = _load_frontend_server_module()
        httpd, thread = self._start_server(server_module)

        try:
            url = f"http://127.0.0.1:{httpd.server_port}/api/reset"
            payload = b"{}"
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req) as resp:
                self.assertEqual(resp.status, 200)
                body = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(body.get("ok"))
            self.assertIn("state", body)
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
