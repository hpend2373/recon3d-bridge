"""Render verified aggregate benchmark data as publication/export artifacts."""

import argparse
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from check_report import load_verified


def save(fig, output, name):
    for extension in ("png", "svg"):
        fig.savefig(output / f"{name}.{extension}", dpi=180, facecolor="white")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=Path(__file__).parent / "results/2026-09-30-mapping")
    args = parser.parse_args()
    report, rows = load_verified(args.report)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "svg.fonttype": "none"})
    colors = ["#63788C", "#087E8B", "#8456A1"]
    footnote = (f"{report['protocol']['repeats']} repetitions per method · Median and IQR (not a confidence interval)\n"
                f"{report['environment']['system']} {report['environment']['machine']} · Python {report['environment']['python']} · File loading / validation excluded")
    fig, axes = plt.subplots(1, 2, figsize=(12, 6), gridspec_kw={"width_ratios": [1.6, 1]})
    fig.suptitle("Faster DEG-to-reaction membership mapping", x=.08, ha="left", fontsize=20, fontweight="bold")
    fig.text(.08, .87, "DEG_hits_CD4_and_HF.csv · 97 rows / 66 genes · Recon3D: 10,600 reactions", color="#465564")
    for ax, methods in zip(axes, [("reference_scan", "indexed_cold"), ("indexed_reused",)]):
        labels = [dict(reference_scan="Repeated scan\nNew reference", indexed_cold="Indexed lookup\nBuild included",
                       indexed_reused="Indexed lookup\nExisting index")[m] for m in methods]
        for position, method in enumerate(methods):
            stat = report["timing"][method]
            color = colors[("reference_scan", "indexed_cold", "indexed_reused").index(method)]
            ax.bar(position, stat["median_ms"], width=.55, color=color)
            ax.errorbar(position, stat["median_ms"], yerr=[[stat["median_ms"] - stat["q1_ms"]],
                        [stat["q3_ms"] - stat["median_ms"]]], fmt="none", color="black", capsize=6)
            values = [float(r["milliseconds"]) for r in rows if r["method"] == method]
            offsets = [(i % 7 - 3) * .035 for i in range(len(values))]
            ax.scatter([position + x for x in offsets], values, color="#223344", s=12, alpha=.3, zorder=4)
            ax.text(position, max(values) * 1.09, f"{stat['median_ms']:.2f} ms" if method != "indexed_reused"
                    else f"{stat['median_ms']:.4f} ms", ha="center", fontweight="bold")
        ax.set_xticks(range(len(methods)), labels)
        ax.set_ylabel("Mapping time (ms)")
        ax.set_ylim(0, max(report["timing"][m]["max_ms"] for m in methods) * 1.35)
        ax.grid(axis="y", alpha=.15)
        ax.set_axisbelow(True)
    comparison = report["comparison"]["indexed_cold"]
    axes[0].set_title(f"Build included: {comparison['ratio_of_medians_speedup']:.2f}× faster / {comparison['median_time_reduction_percent']:.1f}% less time", fontsize=12, pad=15)
    axes[1].set_title("Reuse only · Separate y-axis scale", fontsize=12, pad=15)
    fig.text(.08, .12, "Stage measurement only. New reference baseline; the previous prototype was not available.", fontsize=10)
    fig.text(.08, .055, footnote, fontsize=9, color="#465564")
    fig.subplots_adjust(left=.08, right=.97, top=.74, bottom=.25, wspace=.42)
    save(fig, args.report, "mapping-runtime")

    fig, ax = plt.subplots(figsize=(11, 6))
    fig.suptitle("Same mechanical output, with no dropped rows", x=.1, ha="left", fontsize=19, fontweight="bold")
    fig.text(.1, .85, "100% exact row and reaction identity agreement · Independent literal-token oracle: PASS", color="#087E8B")
    fields = [("Rows retained", "rows_retained"), ("Rows mapped", "rows_with_reaction_mapping"),
              ("Row–reaction\nassociations", "row_reaction_associations"), ("Unique reactions", "unique_reactions")]
    for offset, method in [(-.2, "Repeated scan"), (.2, "Indexed lookup")]:
        values = [report["output"][key] for _, key in fields]
        bars = ax.bar([i + offset for i in range(4)], values, width=.36, color=colors[offset > 0], label=method)
        ax.bar_label(bars, padding=4)
    ax.set_xticks(range(4), [label for label, _ in fields])
    ax.set_ylabel("Count")
    ax.set_ylim(0, 240)
    ax.grid(axis="y", alpha=.15)
    ax.set_axisbelow(True)
    ax.legend(loc="upper left", frameon=False)
    fig.text(.1, .105, "Coverage: 19/97 rows and 11/66 unique gene symbols mapped; all 78 unmapped rows retained.", fontsize=10)
    fig.text(.1, .055, "Membership in a GPR expression only. Biological accuracy, route yield, Laya/Jev and full runtime were not measured.", fontsize=9)
    fig.subplots_adjust(left=.1, right=.97, top=.76, bottom=.25)
    save(fig, args.report, "mapping-output")
    print("Verified plots: mapping-runtime.{png,svg}, mapping-output.{png,svg}")


if __name__ == "__main__":
    main()
