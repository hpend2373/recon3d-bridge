"""Render verified aggregate benchmark data as publication/export artifacts."""

import argparse
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from check_report import load_verified


def save(fig, output, name):
    for extension in ("png", "svg"):
        path = output / f"{name}.{extension}"
        fig.savefig(path, dpi=180, facecolor="white")
        if extension == "svg":
            path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")
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
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), gridspec_kw={"width_ratios": [1.6, 1]})
    fig.suptitle("Mapping time", fontsize=20, fontweight="bold")
    for ax, methods in zip(axes, [("reference_scan", "indexed_cold"), ("indexed_reused",)]):
        labels = ["Rule-based" if m == "reference_scan" else "Our system" for m in methods]
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
    axes[0].set_title("First use", fontsize=12, pad=15)
    axes[1].set_title("Index reuse", fontsize=12, pad=15)
    fig.subplots_adjust(left=.08, right=.97, top=.78, bottom=.13, wspace=.42)
    save(fig, args.report, "mapping-runtime")

    fig, ax = plt.subplots(figsize=(11, 5))
    fig.suptitle("Mapping results", fontsize=20, fontweight="bold")
    fields = [("Input rows kept", "rows_retained"), ("Rows matched", "rows_with_reaction_mapping"),
              ("Gene–reaction links", "row_reaction_associations"), ("Different reactions", "unique_reactions")]
    metric_colors = ["#63788C", "#087E8B", "#8456A1", "#C68A30"]
    for index, (label, key) in enumerate(fields):
        values = [report["output"][key]] * 2
        offset = (index - 1.5) * .18
        bars = ax.bar([i + offset for i in range(2)], values, width=.16, color=metric_colors[index], label=label)
        ax.bar_label(bars, padding=4)
    ax.set_xticks(range(2), ["Rule-based", "Our system"])
    ax.set_ylabel("Count")
    ax.set_ylim(0, 240)
    ax.grid(axis="y", alpha=.15)
    ax.set_axisbelow(True)
    ax.legend(loc="upper center", bbox_to_anchor=(.5, 1.19), ncol=2, frameon=False, fontsize=10)
    fig.subplots_adjust(left=.1, right=.97, top=.73, bottom=.13)
    save(fig, args.report, "mapping-output")
    print("Verified plots: mapping-runtime.{png,svg}, mapping-output.{png,svg}")


if __name__ == "__main__":
    main()
