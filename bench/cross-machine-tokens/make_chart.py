# bench/cross-machine-tokens/make_chart.py
"""Render site/public/token-chart.svg from a measurement result (or sample)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import lib

# Clearly-labeled illustrative numbers for the pre-measurement placeholder.
SAMPLE_COLD, SAMPLE_WARM = 12000, 3000
DEFAULT_OUT = "site/public/token-chart.svg"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Render the token chart SVG")
    ap.add_argument("--in", dest="inp", default=None, help="result.json path")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--sample", action="store_true", help="render the SAMPLE placeholder")
    args = ap.parse_args(argv)

    if args.sample or not args.inp:
        svg = lib.render_chart_svg(SAMPLE_COLD, SAMPLE_WARM, sample=True)
    else:
        data = json.loads(Path(args.inp).read_text(encoding="utf-8"))
        cold = int(data["cold"]["avg_total_input"])
        warm = int(data["warm"]["avg_total_input"])
        svg = lib.render_chart_svg(cold, warm, sample=False)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg, encoding="utf-8")
    print(f"chart: wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
