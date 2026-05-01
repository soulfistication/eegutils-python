#!/usr/bin/env python3
"""
Convert EEG .dat vectors from microvolts (µV) to tenths of microvolts.

Each input line is one sample; output is the same layout with values × 10.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def convert_file(src: Path, dst: Path) -> int:
    """Read µV integers from src, write tenths-of-µV to dst. Returns line count."""
    count = 0
    dst.parent.mkdir(parents=True, exist_ok=True)
    with src.open("r", encoding="utf-8", errors="replace") as fin, dst.open(
        "w", encoding="utf-8", newline="\n"
    ) as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            value = int(line)
            fout.write(f"{value * 10}\n")
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert EEG .dat files from microvolts to tenths of microvolts."
    )
    parser.add_argument(
        "-i",
        "--input-dir",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Directory containing .dat files (default: script directory)",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: <input-dir>/tenth_microvolt)",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite input files (use with care)",
    )
    args = parser.parse_args()

    input_dir = args.input_dir.resolve()
    if not input_dir.is_dir():
        raise SystemExit(f"Input directory not found: {input_dir}")

    dat_files = sorted(input_dir.glob("*.dat")) + sorted(input_dir.glob("*.DAT"))
    # De-duplicate case-insensitive duplicates on case-preserving filesystems
    seen: set[str] = set()
    unique: list[Path] = []
    for p in dat_files:
        key = p.name.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(p)

    if not unique:
        raise SystemExit(f"No .dat files found in {input_dir}")

    if args.in_place:
        out_root = None
    else:
        out_root = (args.output_dir or (input_dir / "tenth_microvolt")).resolve()

    total_lines = 0
    for src in unique:
        if args.in_place:
            tmp = src.with_suffix(src.suffix + ".tmp")
            n = convert_file(src, tmp)
            tmp.replace(src)
        else:
            assert out_root is not None
            dst = out_root / src.name
            n = convert_file(src, dst)
        total_lines += n
        dest_str = str(src) if args.in_place else str(out_root / src.name)
        print(f"{src.name}: {n} samples -> {dest_str}")

    print(f"Done: {len(unique)} file(s), {total_lines} total samples.")


if __name__ == "__main__":
    main()
