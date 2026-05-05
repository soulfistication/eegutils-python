# Matrix µV → 0.1 µV converter

This folder contains `EG.asc`, a tab-delimited numeric matrix in **microvolts (µV)**.

The script `convert_to_tenth_microvolts.py` converts values into **tenths of a microvolt** (0.1 µV units), commonly used for EEG integer storage.

## Convert (recommended: integer 0.1 µV units)

```bash
python3 convert_to_tenth_microvolts.py EG.asc --as-int
```

This writes `EG_0p1uV.asc` (same shape, scaled by 10, rounded half-up to integers).

## Convert (keep scaled floats)

```bash
python3 convert_to_tenth_microvolts.py EG.asc
```

## Output delimiter

By default the output uses tabs. To write space-delimited:

```bash
python3 convert_to_tenth_microvolts.py EG.asc --as-int --delimiter space
```

