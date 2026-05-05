#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional


SETUP_BYTES = 900

# Known offsets within the first 900 bytes of SETUP for common CNT files
OFF_PNTS = 368        # uint16 pnts
OFF_NCHANNELS = 370   # uint16 nchannels
OFF_RATE = 376        # uint16 rate (Hz)
OFF_EVENTPOS = 886    # int32 EventTablePos


def put_u16_le(buf: bytearray, off: int, v: int) -> None:
    buf[off:off + 2] = struct.pack("<H", v & 0xFFFF)


def put_i32_le(buf: bytearray, off: int, v: int) -> None:
    buf[off:off + 4] = struct.pack("<i", int(v))


def starts_with(s: str, prefix: str) -> bool:
    return s.startswith(prefix)


def split_tokens(line: str) -> List[str]:
    # Equivalent to the C whitespace tokenization
    return line.split()


def parse_int_after(line: str, prefix: str) -> Optional[int]:
    if not line.startswith(prefix):
        return None
    rest = line[len(prefix):].strip()
    m = re.match(r"[-+]?\d+", rest)
    return int(m.group(0)) if m else None


@dataclass(frozen=True)
class TeegTag:
    teeg: int = 1
    size: int = 0
    offset: int = 0

    def pack(self) -> bytes:
        # C layout: unsigned char Teeg; long Size; long Offset;
        # On 16-bit Turbo C, long is 4 bytes, little-endian. No packing bytes due to pragma pack(1).
        return struct.pack("<Bii", self.teeg & 0xFF, int(self.size), int(self.offset))


def pack_electloc(label: str) -> bytes:
    """
    Pack the 75-byte ELECTLOC structure used by many Neuroscan CNT files.
    This matches the C struct with #pragma pack(1).
    """
    # C struct field sizes:
    # 10s, b, b, b, b, b, H, b, b,
    # f, f, f, f, f, f, f, h, b, b,
    # f, f, f, b, b, b, B, B, B, B,
    # b, f
    fmt = "<10s5bH2b7fh2b3f3b4Bbf"
    assert struct.calcsize(fmt) == 75

    lab = (label or "").encode("ascii", "ignore")[:9]  # C code copies up to 9 and nul-terminates
    lab = lab + b"\x00"  # ensure at least one terminator byte
    lab = lab[:10].ljust(10, b"\x00")

    # Defaults mirror the C code: mostly zeros, n=1, sensitivity=1.0, calib=1.0
    reference = 0
    skip = 0
    reject = 0
    display = 0
    bad = 0
    n = 1
    avg_reference = 0
    clip_add = 0

    x_coord = 0.0
    y_coord = 0.0
    veog_wt = 0.0
    veog_std = 0.0
    snr = 0.0
    heog_wt = 0.0
    heog_std = 0.0

    baseline = 0  # int16
    filtered = 0
    fsp = 0

    aux1_wt = 0.0
    aux1_std = 0.0
    sensitivity = 1.0

    gain = 0
    hipass = 0
    lopass = 0

    page = 0
    size = 0
    impedance = 0
    physical_chnl = 0

    rectify = 0
    calib = 1.0

    return struct.pack(
        fmt,
        lab,
        reference, skip, reject, display, bad,
        n,
        avg_reference, clip_add,
        x_coord, y_coord, veog_wt, veog_std, snr, heog_wt, heog_std,
        baseline,
        filtered, fsp,
        aux1_wt, aux1_std, sensitivity,
        gain, hipass, lopass,
        page, size, impedance, physical_chnl,
        rectify,
        calib,
    )


SKIP_PREFIXES = (
    "Epoch ",
    "ASCII output of file",
    "number of channels=",
    "Epoched output mode",
    "Continuous output mode",
    "Start point",
    "Stop  point",
)


def is_data_line(line: str) -> bool:
    if not line:
        return False
    return not any(line.startswith(p) for p in SKIP_PREFIXES)


def find_nchannels(lines: Iterable[str]) -> int:
    for raw in lines:
        line = raw.strip()
        v = parse_int_after(line, "number of channels=")
        if v is not None:
            return v
    raise ValueError("Could not read 'number of channels=' from ASCII input.")


def find_labels_after_header(lines: Iterable[str], nch: int) -> List[str]:
    """
    In the C program this is: next non-empty line after skipping mode/start/stop lines
    that has at least nch tokens.
    """
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if (
            starts_with(line, "Epoched output mode")
            or starts_with(line, "Continuous output mode")
            or starts_with(line, "Start point")
            or starts_with(line, "Stop  point")
        ):
            continue

        toks = split_tokens(line)
        if len(toks) >= nch:
            return [t[:10] for t in toks[:nch]]

    raise ValueError("Could not find channel label row in ASCII input.")


def uv_to_int16(uv: float) -> int:
    # C code: raw = uv * 204.8; rounding away from 0 at half; clamp to int16
    raw = uv * 204.8
    v = int(raw + 0.5) if raw >= 0 else int(raw - 0.5)
    if v > 32767:
        v = 32767
    if v < -32768:
        v = -32768
    return v


def main() -> int:
    ap = argparse.ArgumentParser(
        description="ASC2CNT (Python): convert CNTTOASC .ASC back to a minimal Neuroscan .CNT"
    )
    ap.add_argument("base", help="File name without extension (reads .asc, writes .cnt)")
    ap.add_argument("rate_hz", nargs="?", type=int, default=250, help="Sampling rate in Hz (default 250)")
    args = ap.parse_args()

    base = Path(args.base)
    fn_asc = base.with_suffix(".asc")
    fn_cnt = base.with_suffix(".cnt")

    rate = args.rate_hz
    if rate <= 0 or rate >= 50000:
        rate = 250

    print("ASC2CNT (Python): CNTTOASC .ASC -> Neuroscan .CNT")

    text = fn_asc.read_text(errors="replace").splitlines()

    nch = find_nchannels(text)
    if nch <= 0 or nch > 256:
        raise ValueError(f"Invalid channel count: {nch}")

    # Find labels by scanning from the point we found nch
    # (matches intent of the original two-stage scan)
    nch_line_idx = next(
        i for i, l in enumerate(text) if parse_int_after(l.strip(), "number of channels=") is not None
    )
    labels = find_labels_after_header(text[nch_line_idx + 1 :], nch)

    setup = bytearray(SETUP_BYTES)
    put_u16_le(setup, OFF_PNTS, 1)            # continuous: 1 point per read
    put_u16_le(setup, OFF_NCHANNELS, nch)
    put_u16_le(setup, OFF_RATE, rate)
    put_i32_le(setup, OFF_EVENTPOS, 0)        # backpatched later

    nsamples = 0

    with fn_cnt.open("wb+") as out:
        # Header
        out.write(setup)

        # Electrode table
        for lab in labels:
            out.write(pack_electloc(lab))

        # Data section: scan all lines; tolerate non-data lines like the C code
        for raw in text:
            line = raw.strip()
            if not is_data_line(line):
                continue

            toks = split_tokens(line)
            if len(toks) < nch:
                continue

            for j in range(nch):
                uv = float(toks[j])
                s = uv_to_int16(uv)
                out.write(struct.pack("<h", s))
            nsamples += 1

        # Append empty event footer
        event_pos = out.tell()
        out.write(TeegTag().pack())

        # Backpatch EventTablePos
        put_i32_le(setup, OFF_EVENTPOS, event_pos)
        out.seek(0)
        out.write(setup)

    print(f"Wrote {fn_cnt} ({nsamples} samples, {nch} channels, rate {rate} Hz)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())