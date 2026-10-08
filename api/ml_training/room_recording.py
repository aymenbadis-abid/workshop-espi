"""Read a calm-room recording. The simulator scenario is not this room.

Expected CSV columns: ts,temp,hum,gas,simulated
`simulated` is a pipe-separated list of channel names, or empty when every
channel is real. Gas is ignored by the single-channel fit.
"""

from __future__ import annotations

import csv
from pathlib import Path

MIN_SPAN_S = 30 * 60
MIN_ROWS = 360


def load_rows(path: Path) -> list[dict] | None:
    if not path.is_file():
        return None
    rows: list[dict] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = {"ts", "temp", "hum", "gas", "simulated"} - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"{path} is missing columns: {', '.join(sorted(missing))}")
        for raw in reader:
            simulated = [item for item in raw["simulated"].replace(",", "|").split("|") if item]
            rows.append(
                {
                    "ts": int(float(raw["ts"])),
                    "temp": float(raw["temp"]),
                    "hum": float(raw["hum"]),
                    "gas": float(raw["gas"]),
                    "simulated": simulated,
                }
            )
    rows.sort(key=lambda row: row["ts"])
    return rows


def real_rows(rows: list[dict], channels: tuple[str, ...]) -> list[dict]:
    return [row for row in rows if all(channel not in row["simulated"] for channel in channels)]


def long_enough(rows: list[dict]) -> bool:
    if len(rows) < MIN_ROWS:
        return False
    return rows[-1]["ts"] - rows[0]["ts"] >= MIN_SPAN_S
