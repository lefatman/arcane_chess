#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
import tracemalloc
from pathlib import Path

from arcane_interaction_chess.core import Game, setup_standard
from arcane_interaction_chess.engine import Engine
from arcane_interaction_chess.perft import perft


def run_perft(depth: int, repeat: int) -> dict[str, float | int]:
    game = Game()
    setup_standard(game)
    total_nodes = 0
    start = time.perf_counter()
    tracemalloc.start()
    for _ in range(repeat):
        total_nodes += perft(game, depth)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    elapsed = time.perf_counter() - start
    return {
        "depth": depth,
        "repeat": repeat,
        "total_nodes": total_nodes,
        "seconds": elapsed,
        "nodes_per_sec": 0.0 if elapsed <= 0 else total_nodes / elapsed,
        "peak_alloc_bytes": peak,
    }


def run_search(depth: int, repeat: int) -> dict[str, float | int]:
    game = Game()
    setup_standard(game)
    engine = Engine()
    start = time.perf_counter()
    tracemalloc.start()
    found = 0
    for _ in range(repeat):
        mv = engine.best_move(game, depth=depth)
        if mv is not None:
            found += 1
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    elapsed = time.perf_counter() - start
    return {
        "depth": depth,
        "repeat": repeat,
        "best_moves_found": found,
        "seconds": elapsed,
        "searches_per_sec": 0.0 if elapsed <= 0 else repeat / elapsed,
        "peak_alloc_bytes": peak,
    }


def check_thresholds(results: dict[str, dict[str, float | int]], thresholds_path: Path) -> int:
    if not thresholds_path.exists():
        return 0
    thresholds = json.loads(thresholds_path.read_text())
    status = 0
    for bench_name, limits in thresholds.items():
        values = results.get(bench_name)
        if values is None:
            continue
        for metric, expected in limits.items():
            current = float(values.get(metric, 0.0))
            if metric.endswith("_min"):
                base_metric = metric[:-4]
                current = float(values.get(base_metric, 0.0))
                if current < float(expected):
                    print(f"THRESHOLD FAIL {bench_name}.{base_metric}: {current} < {expected}")
                    status = 1
            elif metric.endswith("_max"):
                base_metric = metric[:-4]
                current = float(values.get(base_metric, 0.0))
                if current > float(expected):
                    print(f"THRESHOLD FAIL {bench_name}.{base_metric}: {current} > {expected}")
                    status = 1
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark perft and engine search hot paths")
    parser.add_argument("--perft-depth", type=int, default=4)
    parser.add_argument("--perft-repeat", type=int, default=2)
    parser.add_argument("--search-depth", type=int, default=3)
    parser.add_argument("--search-repeat", type=int, default=10)
    parser.add_argument(
        "--thresholds",
        type=Path,
        default=Path(__file__).with_name("benchmark_thresholds.json"),
    )
    parser.add_argument("--check-thresholds", action="store_true")
    args = parser.parse_args()

    results = {
        "perft": run_perft(depth=args.perft_depth, repeat=args.perft_repeat),
        "search": run_search(depth=args.search_depth, repeat=args.search_repeat),
    }
    print(json.dumps(results, indent=2, sort_keys=True))

    if args.check_thresholds:
        return check_thresholds(results, args.thresholds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
