#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path


_NUM_RE = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$")


def _parse_decimal(token: str) -> Decimal | None:
    token = token.strip()
    if not token or not _NUM_RE.match(token):
        return None
    try:
        return Decimal(token)
    except InvalidOperation:
        return None


def convert_file(
    in_path: Path,
    out_path: Path,
    *,
    multiplier: Decimal,
    output_as_int: bool,
    delimiter: str,
) -> None:
    if delimiter not in {"tab", "space"}:
        raise ValueError("delimiter must be 'tab' or 'space'")

    out_sep = "\t" if delimiter == "tab" else " "

    with in_path.open("r", encoding="utf-8", errors="replace") as fin, out_path.open(
        "w", encoding="utf-8", newline="\n"
    ) as fout:
        for line in fin:
            stripped = line.strip()
            if not stripped:
                fout.write("\n")
                continue

            tokens = stripped.split()
            out_tokens: list[str] = []
            for t in tokens:
                d = _parse_decimal(t)
                if d is None:
                    out_tokens.append(t)
                    continue

                v = d * multiplier
                if output_as_int:
                    v = v.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                    out_tokens.append(str(int(v)))
                else:
                    out_tokens.append(format(float(v), "g"))

            fout.write(out_sep.join(out_tokens) + "\n")


def main() -> int:
    p = argparse.ArgumentParser(
        description=(
            "Convert a numeric matrix from microvolts (uV) to tenths of microvolts "
            "(0.1 uV units)."
        )
    )
    p.add_argument("input", type=Path, help="Input matrix file (e.g. EG.asc)")
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output file path (default: <input>_0p1uV.asc)",
    )
    p.add_argument(
        "--as-int",
        action="store_true",
        help="Round to nearest integer (half-up) after scaling; typical for EEG integer storage.",
    )
    p.add_argument(
        "--delimiter",
        choices=["tab", "space"],
        default="tab",
        help="Delimiter to use when writing output (default: tab).",
    )
    args = p.parse_args()

    in_path: Path = args.input
    if args.output is None:
        out_path = in_path.with_name(f"{in_path.stem}_0p1uV{in_path.suffix}")
    else:
        out_path = args.output

    convert_file(
        in_path,
        out_path,
        multiplier=Decimal("10"),
        output_as_int=bool(args.as_int),
        delimiter=str(args.delimiter),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

