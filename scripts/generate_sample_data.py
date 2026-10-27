#!/usr/bin/env python3
"""Write the seeded NMC811 processing demonstration CSV."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.synthetic import write_sample  # noqa: E402

if __name__ == "__main__":
    path = ROOT / "data" / "samples" / "nmc811_processing_demo.csv"
    frame = write_sample(path, n=24, seed=42)
    print(f"Wrote {len(frame)} rows to {path}")
