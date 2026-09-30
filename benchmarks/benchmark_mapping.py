#!/usr/bin/env python3
"""Measure a mapping-stage reference scan versus cold and reused indices.

Only aggregate measurements and source hashes are written. The supplied DEG
rows and patient expression values are not copied into the public report.
"""

import argparse
import csv
import gc
import hashlib
import io
import json
from pathlib import Path
import platform
import statistics
import time
from datetime import datetime, timezone

from mapping import build_index, indexed_map, oracle_map, output_digest, require_equal, scan_map, validate_inputs


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def quantile(values, q):
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deg", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="New report directory")
    parser.add_argument("--repeats", type=int, default=21)
    args = parser.parse_args()
    if args.repeats < 5:
        parser.error("at least five rounds are required")
    if args.output.exists():
        parser.error("output already exists; choose a new directory to preserve the prior measurement")
    code = {name: sha((Path(__file__).parent / name).read_bytes())
            for name in ("benchmark_mapping.py", "mapping.py", "check_mapping.py")}
    start = time.perf_counter()
    deg_raw = args.deg.read_bytes()
    model_raw = args.model.read_bytes()
    rows = list(csv.DictReader(io.StringIO(deg_raw.decode("utf-8-sig"))))
    model = json.loads(model_raw)
    validate_inputs(rows, model)
    load_seconds = time.perf_counter() - start
    reference = scan_map(rows, model)
    oracle = oracle_map(rows, model)
    require_equal(reference, oracle)
    cached_index = build_index(model)
    require_equal(reference, indexed_map(rows, cached_index))
    methods = {
        "reference_scan": lambda: scan_map(rows, model),
        "indexed_cold": lambda: indexed_map(rows, build_index(model)),
        "indexed_reused": lambda: indexed_map(rows, cached_index),
    }
    timings = []
    names = list(methods)
    for round_id in range(args.repeats):
        # Rotate and reverse order to reduce a systematic timing-order advantage.
        order = names[round_id % 3:] + names[:round_id % 3]
        if round_id % 2:
            order.reverse()
        gc.collect()
        for position, name in enumerate(order):
            begin = time.perf_counter_ns()
            result = methods[name]()
            milliseconds = (time.perf_counter_ns() - begin) / 1_000_000
            require_equal(reference, result)
            timings.append({"round": round_id + 1, "order": position + 1,
                            "method": name, "milliseconds": milliseconds,
                            "output_sha256": output_digest(result)})
    for name, expected in code.items():
        if sha((Path(__file__).parent / name).read_bytes()) != expected:
            raise ValueError("Benchmark source changed during measurement")
    stats = {}
    for name in names:
        values = [row["milliseconds"] for row in timings if row["method"] == name]
        stats[name] = {"n": len(values), "median_ms": statistics.median(values),
                       "q1_ms": quantile(values, .25), "q3_ms": quantile(values, .75),
                       "min_ms": min(values), "max_ms": max(values)}
    baseline_ms = stats["reference_scan"]["median_ms"]
    comparisons = {name: {"ratio_of_medians_speedup": baseline_ms / stats[name]["median_ms"],
                          "median_time_reduction_percent": 100 * (1 - stats[name]["median_ms"] / baseline_ms)}
                   for name in ("indexed_cold", "indexed_reused")}
    mapped = [row for row in reference if row[2]]
    report = {
        "schema_version": 1, "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "DEG symbol to model reaction membership mapping only",
        "baseline": "New reference implementation: repeated reaction scans; not the previous prototype",
        "interpretation": "Output-preserving speed comparison, not an improvement in biological accuracy or route yield",
        "inputs": {"deg_name": args.deg.name, "deg_sha256": sha(deg_raw),
                   "model_name": args.model.name, "model_sha256": sha(model_raw),
                   "deg_rows": len(rows), "unique_gene_symbols": len({r['gene'] for r in rows}),
                   "analysis_groups": len({r['analysis_id'] for r in rows}),
                   "model_reactions": len(model['reactions']), "model_genes": len(model['genes'])},
        "environment": {"system": platform.system(), "machine": platform.machine(),
                        "python": platform.python_version()},
        "protocol": {"repeats": args.repeats, "order": "rotating and alternating",
                     "input_load_and_validation_seconds_excluded_from_each_method": load_seconds,
                     "cold_index_build": "included", "reused_index_build": "excluded and separately shown",
                     "imports_and_model_parsing": "common overhead excluded",
                     "symbol_matching": "exact model gene names; no alias inference",
                     "gpr_semantics": "gene membership only; Boolean activation is not evaluated",
                     "statistic": "median and interquartile range, not a confidence interval"},
        "timing": stats, "comparison": comparisons,
        "output": {"rows_retained": len(reference), "rows_with_reaction_mapping": len(mapped),
                   "unmapped_rows": len(rows) - len(mapped),
                   "unique_mapped_gene_symbols": len({r[1] for r in mapped}),
                   "row_reaction_associations": sum(len(r[2]) for r in reference),
                   "unique_reactions": len({reaction for r in reference for reaction in r[2]}),
                   "exact_row_and_reaction_identity_agreement_percent": 100,
                   "output_sha256": output_digest(reference), "independent_literal_token_oracle": "PASS"},
        "source_sha256": code,
        "unmeasured": ["end-to-end route search time", "Laya inference", "Jev inference",
                       "biological accuracy", "RNA-supported route yield", "intercellular transfer or flux"],
    }
    args.output.mkdir(parents=True)
    with (args.output / "timings.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(timings[0]))
        writer.writeheader()
        writer.writerows(timings)
    (args.output / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"timing": stats, "comparison": comparisons, "output": report["output"]}, indent=2))


if __name__ == "__main__":
    main()
