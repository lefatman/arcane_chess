# arcane_interaction_chess_fullstack_interactive_redo4_solar/frontend/scripts/concurrency_stress.py
from __future__ import annotations

import argparse
import concurrent.futures
import json
import random
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SERVER_PATH = REPO_ROOT / "frontend" / "server.py"


def _request_json(url: str, payload: dict[str, Any] | None = None, timeout: float = 2.0) -> tuple[int, dict[str, Any]]:
    body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="GET" if body is None else "POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            raw = resp.read()
    except urllib.error.HTTPError as e:
        status = int(e.code)
        raw = e.read()
    data = json.loads(raw.decode("utf-8")) if raw else {}
    return status, data


def _wait_ready(base_url: str, deadline_s: float = 10.0) -> None:
    end = time.monotonic() + deadline_s
    while time.monotonic() < end:
        try:
            status, data = _request_json(f"{base_url}/api/state")
            if status == 200 and data.get("ok") is True:
                return
        except Exception:
            pass
        time.sleep(0.05)
    raise RuntimeError("server did not become ready")


def _apply_worker(base_url: str, rounds: int, seed: int, errors: list[str], lock: threading.Lock) -> None:
    rnd = random.Random(seed)
    for _ in range(rounds):
        try:
            status, legal = _request_json(f"{base_url}/api/legal")
            if status != 200 or legal.get("ok") is not True:
                continue
            moves = legal.get("moves") or []
            if not moves:
                continue
            move = moves[rnd.randrange(len(moves))]
            status, data = _request_json(f"{base_url}/api/apply", {"move": move})
            if status == 500 or data.get("ok") is False and "error" in data and "Pending decision id mismatch" in str(data.get("error")):
                with lock:
                    errors.append(f"apply failure status={status} body={data}")
        except Exception as e:
            with lock:
                errors.append(f"apply exception: {e}")


def _undo_worker(base_url: str, rounds: int, errors: list[str], lock: threading.Lock) -> None:
    for _ in range(rounds):
        try:
            status, data = _request_json(f"{base_url}/api/undo", {})
            if status == 500:
                with lock:
                    errors.append(f"undo failure status={status} body={data}")
        except Exception as e:
            with lock:
                errors.append(f"undo exception: {e}")


def _pending_probe_worker(base_url: str, rounds: int, errors: list[str], lock: threading.Lock) -> None:
    last_id: str | None = None
    for _ in range(rounds):
        try:
            status, data = _request_json(f"{base_url}/api/pending")
            if status != 200 or data.get("ok") is not True:
                continue
            pending = data.get("pending")
            if pending is None:
                last_id = None
                continue
            pid = pending.get("id")
            if not isinstance(pid, str) or not pid:
                with lock:
                    errors.append(f"invalid pending id payload={pending}")
            if last_id is not None and pid != last_id:
                with lock:
                    errors.append(f"pending id changed without clear old={last_id} new={pid}")
            last_id = pid
        except Exception as e:
            with lock:
                errors.append(f"pending exception: {e}")


def run_stress(base_url: str, apply_workers: int, undo_workers: int, rounds: int, seed: int) -> None:
    errors: list[str] = []
    lock = threading.Lock()
    with concurrent.futures.ThreadPoolExecutor(max_workers=apply_workers + undo_workers + 1) as ex:
        futures = []
        for i in range(apply_workers):
            futures.append(ex.submit(_apply_worker, base_url, rounds, seed + i, errors, lock))
        for _ in range(undo_workers):
            futures.append(ex.submit(_undo_worker, base_url, rounds, errors, lock))
        futures.append(ex.submit(_pending_probe_worker, base_url, rounds * 2, errors, lock))
        for f in futures:
            f.result()
    if errors:
        raise AssertionError(errors[0])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--rounds", type=int, default=80)
    ap.add_argument("--apply-workers", type=int, default=4)
    ap.add_argument("--undo-workers", type=int, default=4)
    args = ap.parse_args()

    cmd = ["python", str(SERVER_PATH), "--host", args.host, "--port", str(args.port)]
    proc = subprocess.Popen(cmd, cwd=str(REPO_ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    base_url = f"http://{args.host}:{args.port}"
    try:
        _wait_ready(base_url)
        status, reset = _request_json(f"{base_url}/api/newgame", {"white": {}, "black": {}, "rng_seed": args.seed})
        if status != 200 or reset.get("ok") is not True:
            raise RuntimeError(f"failed to set deterministic newgame: status={status} body={reset}")
        run_stress(base_url, args.apply_workers, args.undo_workers, args.rounds, args.seed)
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)


if __name__ == "__main__":
    raise SystemExit(main())
