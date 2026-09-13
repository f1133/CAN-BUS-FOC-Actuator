#!/usr/bin/env python3
"""
BOM sufficiency check: are the parts on hand enough for N boards?

Reads hardware/bom/inventory.csv (what was actually bought / listed) and
hardware/bom/per_board.csv (what the design needs), prints a shortfall table.

Run: python3 tools/check_bom.py [--boards 3]
"""
import argparse
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "hardware" / "bom"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--boards", type=int, default=3)
    n = ap.parse_args().boards

    inv = {r["part"]: r for r in csv.DictReader((ROOT / "inventory.csv").open())}
    need = list(csv.DictReader((ROOT / "per_board.csv").open()))

    # HDR strip is 40 positions each
    if "HDR-1x40-F-SMT" in inv:
        inv["HDR-1x40-F-SMT"]["qty_on_hand"] = str(int(inv["HDR-1x40-F-SMT"]["qty_on_hand"]) * 40)

    rows, blockers, short, tight, bought = [], [], [], [], []
    for r in need:
        part, per = r["part"], int(r["qty_per_board"])
        total = per * n
        have = int(inv[part]["qty_on_hand"]) if part in inv else 0
        status = "OK"
        if part not in inv:
            status = "MISSING"
            blockers.append(part)
        elif have == 0 and "bought" in inv[part]["source"].lower():
            status = f"BOUGHT — confirm you have ≥ {total}"
            bought.append(part)
        elif have == 0:
            status = "QTY UNKNOWN (user-supplied)"
            short.append(part)
        elif have < total:
            status = f"SHORT by {total - have}"
            short.append(part)
        elif have - total <= per // 2:      # less than half a board of spares
            status = f"OK (tight, {have - total} spare)"
            tight.append(part)
        rows.append((part, per, total, have, status))

    w = max(len(r[0]) for r in rows)
    print(f"{'part':{w}}  per  x{n}  have  status")
    for part, per, total, have, status in rows:
        print(f"{part:{w}}  {per:3d}  {total:3d}  {have:4d}  {status}")

    print()
    print(f"MISSING entirely ({len(blockers)}): " + ", ".join(blockers))
    print(f"Bought, count to confirm ({len(bought)}): " + ", ".join(bought))
    print(f"SHORT / qty unknown ({len(short)}): " + ", ".join(short))
    print(f"Tight ({len(tight)}): " + ", ".join(tight))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
