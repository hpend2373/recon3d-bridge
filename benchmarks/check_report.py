"""Independently check recorded timings, frozen source hashes, and guard mutations."""

import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent
REPORT = ROOT / "results/2026-09-30-mapping"


def load_verified(report_dir=REPORT):
    report = json.loads((report_dir / "summary.json").read_text())
    with (report_dir / "timings.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    expected_methods = {"reference_scan", "indexed_cold", "indexed_reused"}
    assert {r["method"] for r in rows} == expected_methods
    repeats = report["protocol"]["repeats"]
    assert len(rows) == repeats * 3 and repeats >= 5
    for number in range(1, repeats + 1):
        batch = [r for r in rows if int(r["round"]) == number]
        assert {r["method"] for r in batch} == expected_methods and len(batch) == 3
        assert {int(r["order"]) for r in batch} == {1, 2, 3}
    for row in rows:
        assert row["output_sha256"] == report["output"]["output_sha256"]
        assert math.isfinite(float(row["milliseconds"])) and float(row["milliseconds"]) > 0
    for name in expected_methods:
        values = [float(r["milliseconds"]) for r in rows if r["method"] == name]
        quartiles = statistics.quantiles(values, n=4, method="inclusive")
        calculated = dict(n=len(values), median_ms=statistics.median(values),
                          q1_ms=quartiles[0], q3_ms=quartiles[2], min_ms=min(values), max_ms=max(values))
        for key, value in calculated.items():
            assert math.isclose(value, report["timing"][name][key], rel_tol=1e-12, abs_tol=1e-12)
    baseline = report["timing"]["reference_scan"]["median_ms"]
    for name, comparison in report["comparison"].items():
        duration = report["timing"][name]["median_ms"]
        assert math.isclose(baseline / duration, comparison["ratio_of_medians_speedup"])
        assert math.isclose(100 * (1 - duration / baseline), comparison["median_time_reduction_percent"])
    for name, digest in report["source_sha256"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
    assert report["output"]["rows_retained"] == report["inputs"]["deg_rows"]
    assert report["output"]["rows_with_reaction_mapping"] + report["output"]["unmapped_rows"] == report["inputs"]["deg_rows"]
    assert report["output"]["independent_literal_token_oracle"] == "PASS"
    return report, rows


def check_mutation():
    # Only mutate an isolated scratch copy; the measured source stays frozen.
    source = (ROOT / "mapping.py").read_text()
    original = '    if candidate != reference:\n        raise ValueError("Mapping mismatch: row identities or exact reaction memberships differ")'
    assert source.count(original) == 1
    with tempfile.TemporaryDirectory() as folder:
        scratch = Path(folder)
        (scratch / "mapping.py").write_text(source.replace(original, "    pass"))
        (scratch / "check_mapping.py").write_bytes((ROOT / "check_mapping.py").read_bytes())
        result = subprocess.run([sys.executable, str(scratch / "check_mapping.py")],
                                capture_output=True, text=True)
        assert result.returncode != 0 and "Expected a failed gate" in result.stderr


if __name__ == "__main__":
    load_verified()
    check_mutation()
    print("Report statistics, source identity, and scratch mutation: PASS")
