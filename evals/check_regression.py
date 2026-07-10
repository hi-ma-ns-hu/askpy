"""
evals/check_regression.py — metric regression gate for CI.

Production context: this is the offline eval pattern used by most ML teams.
Before every deploy, run the eval harness and compare against a saved baseline.
If any metric drops beyond the tolerance, block the deploy. Same idea as a
test suite, but for model/pipeline quality instead of code correctness.

Usage:
  # generate current results
  python -m evals.run_evals --no-cache

  # compare against baseline (fails with exit 1 on regression)
  python -m evals.check_regression

  # promote current results to baseline once you're happy
  python -m evals.check_regression --promote

Files:
  evals/results_baseline.json  — committed, represents known-good quality
  evals/results_current.json   — written by run_evals.py, gitignored

Tolerance: 5% relative drop. If baseline faithfulness is 0.80, current must
be >= 0.76 to pass. Absolute drops < 0.03 are ignored regardless (noise floor).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BASELINE = Path(__file__).parent / "results_baseline.json"
CURRENT  = Path(__file__).parent / "results_current.json"

METRICS   = ["relevance", "faithfulness", "source_fit"]
TOLERANCE = 0.05   # 5% relative drop triggers failure
NOISE     = 0.03   # absolute drops smaller than this are ignored (judge noise)


def load_metrics(path: Path) -> dict[str, float]:
    if not path.exists():
        print(f"file not found: {path}")
        sys.exit(2)
    data = json.loads(path.read_text())
    missing = [m for m in METRICS if m not in data]
    if missing:
        print(f"missing metrics in {path.name}: {missing}")
        sys.exit(2)
    return {m: float(data[m]) for m in METRICS}


def promote() -> None:
    """Copy current results to baseline."""
    if not CURRENT.exists():
        print(f"no current results at {CURRENT} — run evals first")
        sys.exit(2)
    BASELINE.write_text(CURRENT.read_text())
    data = json.loads(CURRENT.read_text())
    print(f"promoted to baseline:")
    for m in METRICS:
        print(f"  {m}: {data[m]:.4f}")


def check() -> None:
    current  = load_metrics(CURRENT)
    baseline = load_metrics(BASELINE)

    regressions = []
    improvements = []

    for metric in METRICS:
        base = baseline[metric]
        curr = current[metric]
        drop = base - curr
        drop_pct = drop / base if base > 0 else 0

        if drop > NOISE and drop_pct > TOLERANCE:
            regressions.append((metric, base, curr, drop_pct))
        elif curr > base + NOISE:
            improvements.append((metric, base, curr))

    if improvements:
        print("improvements:")
        for metric, base, curr in improvements:
            print(f"  {metric}: {base:.4f} → {curr:.4f}  (+{(curr-base)/base*100:.1f}%)")

    if regressions:
        print("\nREGRESSIONS DETECTED:")
        for metric, base, curr, pct in regressions:
            print(f"  {metric}: {base:.4f} → {curr:.4f}  (-{pct*100:.1f}%)")
        print("\nblock deploy — run 'python -m evals.check_regression --promote' only after investigation")
        sys.exit(1)

    print("\nall metrics within tolerance — OK")
    print("run 'python -m evals.check_regression --promote' to update baseline")


if __name__ == "__main__":
    if "--promote" in sys.argv:
        promote()
    else:
        check()
