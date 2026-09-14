#!/usr/bin/env python3
"""
Verify the generated KiCad project against tools/board_design.py.

Runs kicad-cli to extract the netlist KiCad itself sees from the schematic,
then checks it pin-for-pin against the design.  A mismatch means a label or a
power symbol did not land on the pin it was meant to, which is exactly the
class of bug that a generated schematic can hide.

Also cross-checks component references against hardware/bom/single_board_bom.csv.

Run: python3 tools/check_design.py
"""
from __future__ import annotations

import csv
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sexp import parse, find, first  # noqa: E402
import board_design as bd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SCH = ROOT / "hardware" / "kicad" / "can-foc-actuator.kicad_sch"
BOM = ROOT / "hardware" / "bom" / "single_board_bom.csv"


# Present in single_board_bom.csv but not as schematic symbols: the two pad
# groups of U6's socket footprint, and the off-board thermistor.
OFF_SCHEMATIC = {"J7", "J8", "RT1"}


def design_nets():
    """net -> {(ref, pin)} for connected pins, plus the set of no-connect pins."""
    nets, ncs = defaultdict(set), set()
    for c in bd.C:
        if c["ref"].startswith("#"):          # power flags carry no netlist node
            continue
        for pin, net in c["pins"].items():
            (nets[net].add((c["ref"], pin)) if net else ncs.add((c["ref"], pin)))
    return nets, ncs


def kicad_nets():
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "net.net"
        r = subprocess.run(["kicad-cli", "sch", "export", "netlist", "--output", str(out), str(SCH)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit(f"kicad-cli failed:\n{r.stdout}\n{r.stderr}")
        root = parse(out.read_text())[0]
    nets, ncs = defaultdict(set), set()
    for n in find(first(root, "nets"), "net"):
        name = first(n, "name")[1]
        nodes = {(first(node, "ref")[1], first(node, "pin")[1]) for node in find(n, "node")}
        nodes = {(r, p) for r, p in nodes if not r.startswith("#")}
        if name.startswith("unconnected-("):     # KiCad's name for a no-connect pin
            ncs |= nodes
            continue
        nets[name.lstrip("/")] |= nodes          # local labels get a sheet-path prefix
    comps = {}
    for c in find(first(root, "components"), "comp"):
        ref = first(c, "ref")[1]
        fp = first(c, "footprint")
        val = first(c, "value")
        comps[ref] = (val[1] if val else "", fp[1] if fp else "")
    return nets, ncs, comps


def main() -> int:
    errs, warns = [], []
    want, want_nc = design_nets()
    got, got_nc, comps = kicad_nets()

    if want_nc != got_nc:
        for n in sorted(want_nc - got_nc):
            errs.append(f"pin {n[0]}.{n[1]} should be no-connect but KiCad has it on a net")
        for n in sorted(got_nc - want_nc):
            errs.append(f"pin {n[0]}.{n[1]} is unconnected in the schematic but the design nets it")

    # KiCad may rename a net it considers unnamed; ours are all labelled.
    missing = set(want) - set(got)
    extra = {n for n in set(got) - set(want) if got[n]}
    for n in sorted(missing):
        errs.append(f"net {n!r} in design but not in the schematic KiCad read")
    for n in sorted(extra):
        errs.append(f"net {n!r} appears in the schematic but is not in the design: {sorted(got[n])}")
    for n in sorted(set(want) & set(got)):
        if want[n] != got[n]:
            only_d = sorted(want[n] - got[n])
            only_k = sorted(got[n] - want[n])
            errs.append(f"net {n!r} differs - design-only {only_d}, schematic-only {only_k}")

    # every non-power component from the design must be present, with its footprint
    for c in bd.C:
        if c["ref"].startswith("#"):
            continue
        if c["ref"] not in comps:
            errs.append(f"{c['ref']} missing from the schematic")
            continue
        val, fp = comps[c["ref"]]
        if c["fp"] and fp != c["fp"]:
            errs.append(f"{c['ref']} footprint is {fp!r}, design says {c['fp']!r}")
        if val != c["value"]:
            errs.append(f"{c['ref']} value is {val!r}, design says {c['value']!r}")

    # cross-check references against the human BOM
    bom_refs = set()
    for row in csv.DictReader(BOM.open(encoding="utf-8")):
        for r in re.split(r"[ ,]+", (row["ref"] or "").strip()):
            if r and not r.startswith(("PCB", "M3", "W")) and r not in OFF_SCHEMATIC:
                bom_refs.add(r)
    design_refs = {c["ref"] for c in bd.C if not c["ref"].startswith(("#", "MH"))}
    for r in sorted(bom_refs - design_refs):
        warns.append(f"{r} is in single_board_bom.csv but not in the KiCad design")
    for r in sorted(design_refs - bom_refs):
        warns.append(f"{r} is in the KiCad design but not in single_board_bom.csv")

    for n, v in sorted((n, v) for n, v in got.items() if len(v) == 1):
        warns.append(f"net {n!r} reaches only one pin: {sorted(v)}")
    print(f"no-connect pins: {len(got_nc)} (design says {len(want_nc)})")

    print(f"design: {len(bd.C)} symbols, {len(want)} nets")
    print(f"kicad : {len(comps)} components, {len(got)} nets with pins")
    for w in warns:
        print("WARN ", w)
    for e in errs:
        print("ERROR", e)
    if errs:
        print(f"\n{len(errs)} mismatch(es)")
        return 1
    print("\nOK: the netlist KiCad extracts matches board_design.py exactly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
