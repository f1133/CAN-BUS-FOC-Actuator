#!/usr/bin/env python3
"""
Generate the KiCad 7 project for the CAN-BUS FOC actuator carrier from
tools/board_design.py.  Nothing under hardware/kicad/ is hand-edited.

Standard parts reference the stock KiCad libraries (every install has them);
only the three non-standard symbols live in the project library canfoc.

Run: python3 tools/gen_kicad.py
"""
from __future__ import annotations

import json
import math
import sys
import uuid as _uuid
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sexp import parse, find, first, dumps, Sym  # noqa: E402
import board_design as bd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "hardware" / "kicad"
LIBDIR = OUT / "lib"
PRETTY = LIBDIR / "canfoc.pretty"
KISYM = Path("/usr/share/kicad/symbols")
PROJECT = "can-foc-actuator"

# Deterministic UUIDs so regenerating does not churn the file.
NS = _uuid.UUID("7f1c9a52-0b3e-4a1b-9a77-5f6d2c0e4b10")
def uid(*parts) -> str:
    return str(_uuid.uuid5(NS, "|".join(str(p) for p in parts)))

POWER_SYMS = {"GND": "power:GND", "+3V3": "power:+3V3", "+5V": "power:+5V",
              "VBUS": "power:VBUS", "VDDA": "power:VDDA"}

# ---------------------------------------------------------------------------
# Project symbol library (KiCad 7 format)
# ---------------------------------------------------------------------------
def _pin(typ, num, name, x, y, rot, length=5.08, nsize=1.0):
    return [Sym("pin"), Sym(typ), Sym("line"),
            [Sym("at"), Sym(f"{x}"), Sym(f"{y}"), Sym(f"{rot}")],
            [Sym("length"), Sym(f"{length}")],
            [Sym("name"), name, [Sym("effects"), [Sym("font"), [Sym("size"), Sym(f"{nsize}"), Sym(f"{nsize}")]]]],
            [Sym("number"), num, [Sym("effects"), [Sym("font"), [Sym("size"), Sym("1.0"), Sym("1.0")]]]]]


def _prop(name, value, x, y, hide=False, justify=None):
    eff = [Sym("effects"), [Sym("font"), [Sym("size"), Sym("1.27"), Sym("1.27")]]]
    if justify:
        eff.append([Sym("justify"), Sym(justify)])
    if hide:
        eff.append(Sym("hide"))
    return [Sym("property"), name, value, [Sym("at"), Sym(f"{x}"), Sym(f"{y}"), Sym("0")], eff]


def _rect(x1, y1, x2, y2):
    return [Sym("rectangle"),
            [Sym("start"), Sym(f"{x1}"), Sym(f"{y1}")], [Sym("end"), Sym(f"{x2}"), Sym(f"{y2}")],
            [Sym("stroke"), [Sym("width"), Sym("0.254")], [Sym("type"), Sym("default")]],
            [Sym("fill"), [Sym("type"), Sym("background")]]]


def _symbol(name, fp, datasheet, descr, w, h, pins, prop_off=2.54):
    body = [Sym("symbol"), f"{name}_0_1", _rect(-w, h, w, -h)]
    unit = [Sym("symbol"), f"{name}_1_1"] + pins
    return [Sym("symbol"), name,
            [Sym("pin_names"), [Sym("offset"), Sym("0.254")]],
            [Sym("in_bom"), Sym("yes")], [Sym("on_board"), Sym("yes")],
            _prop("Reference", "U", -w, h + prop_off, justify="left"),
            _prop("Value", name, -w, -h - prop_off, justify="left"),
            _prop("Footprint", fp, 0, 0, hide=True),
            _prop("Datasheet", datasheet, 0, 0, hide=True),
            _prop("ki_description", descr, 0, 0, hide=True),
            body, unit]


def build_project_symbols():
    # --- INA240A1D: pin numbers from KiCad upstream Amplifier_Current/INA240A1D
    ina = _symbol(
        "INA240A1D", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
        "http://www.ti.com/lit/ds/symlink/ina240.pdf",
        "Bidirectional zero-drift current-sense amplifier, 20 V/V, -4..80 V common mode, "
        "enhanced PWM rejection, SOIC-8",
        7.62, 10.16, [
            _pin("input", "8", "IN+", -12.7, 5.08, 0),
            _pin("input", "1", "IN-", -12.7, 0, 0),
            _pin("output", "5", "OUT", 12.7, 5.08, 180),
            _pin("passive", "7", "REF1", 12.7, -2.54, 180),
            _pin("passive", "3", "REF2", 12.7, -7.62, 180),
            _pin("power_in", "6", "V+", 0, 15.24, 270),
            _pin("power_in", "2", "GND", -2.54, -15.24, 90),
            _pin("power_in", "4", "GND", 2.54, -15.24, 90),
        ])
    # --- SimpleFOC Mini: H1 = 1..10, P1 = 11..13 (OUT3, OUT2, OUT1)
    mini = _symbol(
        "SimpleFOC_Mini", "canfoc:SimpleFOC_Mini_Socket",
        "https://github.com/simplefoc/SimpleFOCMini",
        "SimpleFOC Mini v1.0 (DRV8313) three-phase driver module. Pins 1-10 are header H1, "
        "11-13 are header P1 (OUT3, OUT2, OUT1). VM/GND arrive at the module screw terminal.",
        12.7, 20.32, [
            _pin("input", "3", "IN1", -17.78, 15.24, 0),
            _pin("input", "5", "IN2", -17.78, 12.7, 0),
            _pin("input", "7", "IN3", -17.78, 10.16, 0),
            _pin("input", "9", "EN", -17.78, 5.08, 0),
            _pin("input", "8", "nSLEEP", -17.78, 2.54, 0),
            _pin("input", "6", "nRESET", -17.78, 0, 0),
            _pin("open_collector", "10", "nFAULT", -17.78, -5.08, 0),
            _pin("output", "13", "OUT1", 17.78, 15.24, 180),
            _pin("output", "12", "OUT2", 17.78, 12.7, 180),
            _pin("output", "11", "OUT3", 17.78, 10.16, 180),
            _pin("power_out", "2", "3V3_OUT_DO_NOT_CONNECT", 0, 25.4, 270),
            _pin("power_in", "1", "GND", -5.08, -25.4, 90),
            _pin("power_in", "4", "GND", 5.08, -25.4, 90),
        ])
    # --- MP1584EN buck module
    buck = _symbol(
        "MP1584_Module", "canfoc:MP1584_Module_4pin", "",
        "MP1584EN mini buck module, 4 pads. Set the trimmer to 5.00 V before fitting.",
        10.16, 7.62, [
            _pin("power_in", "1", "IN+", -15.24, 5.08, 0),
            _pin("power_in", "2", "IN-", -15.24, -5.08, 0),
            _pin("power_out", "3", "OUT+", 15.24, 5.08, 180),
            _pin("power_in", "4", "OUT-", 15.24, -5.08, 180),
        ])
    lib = [Sym("kicad_symbol_lib"), [Sym("version"), Sym("20220914")],
           [Sym("generator"), Sym("canfoc_gen")], ina, mini, buck]
    LIBDIR.mkdir(parents=True, exist_ok=True)
    (LIBDIR / "canfoc.kicad_sym").write_text(dumps(lib) + "\n")
    return {"canfoc:INA240A1D": ina, "canfoc:SimpleFOC_Mini": mini, "canfoc:MP1584_Module": buck}


# ---------------------------------------------------------------------------
# Footprints
# ---------------------------------------------------------------------------
VENDOR_MINI = ROOT / "hardware" / "vendor" / "simplefocmini" / "PCB_simplefocmini_2022-04-20.json"
EASYEDA_UNIT_MM = 0.254   # 1 internal unit; confirmed by the 2.54 mm header pitch


def mini_geometry():
    """Socket geometry read straight out of the vendor EasyEDA board file.

    Returns pads {number: (x, y)} and the board outline (x0, y0, x1, y1), in mm
    relative to H1 pad 1, which is the footprint origin.  EasyEDA's Y axis runs
    down the screen, same as KiCad's, so no flip is needed.  P1 pads 1-3 are
    renumbered 11-13 (OUT3, OUT2, OUT1) so the socket has one flat pin space.
    """
    d = json.loads(VENDOR_MINI.read_text())
    shapes = d.get("shape") or d["dataStr"]["shape"]

    headers, outline = {}, []
    for sh in shapes:
        fields = sh.split("~")
        if fields[0] == "TRACK" and fields[2] == "10":          # board outline layer
            v = [float(x) for x in fields[4].split()]
            outline += list(zip(v[0::2], v[1::2]))
        if not sh.startswith("LIB"):
            continue
        parts = sh.split("#@$")
        des = next((q.split("~")[10] for q in parts if q.startswith("TEXT~P~")), None)
        if des in ("H1", "P1"):
            headers[des] = {q.split("~")[8]: (float(q.split("~")[2]), float(q.split("~")[3]))
                            for q in parts if q.startswith("PAD~")}
    if not {"H1", "P1"} <= headers.keys() or not outline:
        raise SystemExit(f"{VENDOR_MINI.name}: could not find H1, P1 and the board outline")

    ox, oy = headers["H1"]["1"]

    def mm(x, y):
        return (round((x - ox) * EASYEDA_UNIT_MM, 3), round((y - oy) * EASYEDA_UNIT_MM, 3))

    pads = {n: mm(*xy) for n, xy in headers["H1"].items()}
    pads.update({str(int(n) + 10): mm(*xy) for n, xy in headers["P1"].items()})
    pts = [mm(x, y) for x, y in outline]
    return pads, (min(p[0] for p in pts), min(p[1] for p in pts),
                  max(p[0] for p in pts), max(p[1] for p in pts))


MINI_PADS, MINI_OUTLINE = mini_geometry()
MP1584_PITCH_Y = 17.78  # TO VERIFY against your module with calipers


def _pad(num, x, y, rect=False, drill=1.0, size=1.8):
    shape = "rect" if rect else "circle"
    return (f'  (pad "{num}" thru_hole {shape} (at {x:.3f} {y:.3f}) (size {size} {size}) '
            f'(drill {drill}) (layers "*.Cu" "*.Mask") (tstamp {uid("pad", num, x, y)}))')


def _fp(name, descr, tags, body, keepout=""):
    return "\n".join([
        f'(footprint "{name}" (version 20221018) (generator canfoc_gen)',
        '  (layer "F.Cu")',
        f'  (descr "{descr}")',
        f'  (tags "{tags}")',
        '  (attr through_hole)',
        body, keepout, ")"]).replace("\n\n", "\n")


def build_footprints():
    PRETTY.mkdir(parents=True, exist_ok=True)
    # ---- SimpleFOC Mini socket -------------------------------------------
    x0, y0, x1, y1 = MINI_OUTLINE      # the module's real board edge, from the vendor file
    lines = [_pad(n, *MINI_PADS[n], rect=(n == "1")) for n in
             sorted(MINI_PADS, key=int)]
    silk = []
    for (a, b, c, d) in ((x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)):
        silk.append(f'  (fp_line (start {a:.3f} {b:.3f}) (end {c:.3f} {d:.3f}) '
                    f'(stroke (width 0.12) (type solid)) (layer "F.SilkS") (tstamp {uid("silk", a, b, c, d)}))')
    for (a, b, c, d) in ((x0 - 0.5, y0 - 0.5, x1 + 0.5, y0 - 0.5), (x1 + 0.5, y0 - 0.5, x1 + 0.5, y1 + 0.5),
                         (x1 + 0.5, y1 + 0.5, x0 - 0.5, y1 + 0.5), (x0 - 0.5, y1 + 0.5, x0 - 0.5, y0 - 0.5)):
        silk.append(f'  (fp_line (start {a:.3f} {b:.3f}) (end {c:.3f} {d:.3f}) '
                    f'(stroke (width 0.05) (type solid)) (layer "F.CrtYd") (tstamp {uid("crt", a, b, c, d)}))')
    texts = [
        f'  (fp_text reference "REF**" (at {(x0+x1)/2:.3f} {y0-1.5:.3f}) (layer "F.SilkS") '
        f'(effects (font (size 1 1) (thickness 0.15))) (tstamp {uid("ref")}))',
        f'  (fp_text value "SimpleFOC_Mini_Socket" (at {(x0+x1)/2:.3f} {y1+1.5:.3f}) (layer "F.Fab") '
        f'(effects (font (size 1 1) (thickness 0.15))) (tstamp {uid("val")}))',
        f'  (fp_text user "H1 pin1" (at {MINI_PADS["1"][0]+2.2:.3f} {MINI_PADS["1"][1]-1.6:.3f}) (layer "F.SilkS") '
        f'(effects (font (size 0.7 0.7) (thickness 0.1))) (tstamp {uid("t1")}))',
        f'  (fp_text user "OUT1" (at {MINI_PADS["13"][0]:.3f} {MINI_PADS["13"][1]+1.8:.3f}) (layer "F.SilkS") '
        f'(effects (font (size 0.7 0.7) (thickness 0.1))) (tstamp {uid("t2")}))',
        f'  (fp_text user "2=3V3 NC" (at {MINI_PADS["2"][0]-3.0:.3f} {MINI_PADS["2"][1]+1.6:.3f}) (layer "F.SilkS") '
        f'(effects (font (size 0.7 0.7) (thickness 0.1))) (tstamp {uid("t3")}))',
    ]
    (PRETTY / "SimpleFOC_Mini_Socket.kicad_mod").write_text(_fp(
        "SimpleFOC_Mini_Socket",
        "Socket for a SimpleFOC Mini v1.0 (DRV8313) module. Pads 1-10 = module header H1, "
        "11-13 = header P1 (OUT3 OUT2 OUT1). Pads and outline are generated from the module's own "
        "EasyEDA board file in hardware/vendor/simplefocmini/. The silkscreen is the real module edge "
        "%.1f x %.1f mm - keep it clear. Pad 2 is the module 3.3V LDO output, leave unconnected." % (
            MINI_OUTLINE[2] - MINI_OUTLINE[0], MINI_OUTLINE[3] - MINI_OUTLINE[1]),
        "simplefoc mini drv8313 module socket",
        "\n".join(texts + lines + silk)) + "\n")

    # ---- MP1584 module ----------------------------------------------------
    pads = {"1": (0.0, 0.0), "2": (0.0, 2.54), "3": (-MP1584_PITCH_Y, 0.0), "4": (-MP1584_PITCH_Y, 2.54)}
    lines = [_pad(n, *pads[n], rect=(n == "1")) for n in sorted(pads, key=int)]
    bx0, bx1 = -MP1584_PITCH_Y - 3.0, 3.0
    by0, by1 = -3.0, 5.54
    silk = []
    for (a, b, c, d) in ((bx0, by0, bx1, by0), (bx1, by0, bx1, by1), (bx1, by1, bx0, by1), (bx0, by1, bx0, by0)):
        silk.append(f'  (fp_line (start {a:.3f} {b:.3f}) (end {c:.3f} {d:.3f}) '
                    f'(stroke (width 0.12) (type solid)) (layer "F.SilkS") (tstamp {uid("ms", a, b, c, d)}))')
    texts = [
        f'  (fp_text reference "REF**" (at {(bx0+bx1)/2:.3f} {by0-1.5:.3f}) (layer "F.SilkS") '
        f'(effects (font (size 1 1) (thickness 0.15))) (tstamp {uid("mref")}))',
        f'  (fp_text value "MP1584_Module_4pin" (at {(bx0+bx1)/2:.3f} {by1+1.5:.3f}) (layer "F.Fab") '
        f'(effects (font (size 1 1) (thickness 0.15))) (tstamp {uid("mval")}))',
        f'  (fp_text user "VERIFY PITCH" (at {(bx0+bx1)/2:.3f} {by1-1.2:.3f}) (layer "F.SilkS") '
        f'(effects (font (size 0.8 0.8) (thickness 0.12))) (tstamp {uid("mwarn")}))',
        f'  (fp_text user "IN" (at 1.6 1.27) (layer "F.SilkS") '
        f'(effects (font (size 0.8 0.8) (thickness 0.12))) (tstamp {uid("min")}))',
        f'  (fp_text user "OUT" (at {-MP1584_PITCH_Y-1.8:.3f} 1.27) (layer "F.SilkS") '
        f'(effects (font (size 0.8 0.8) (thickness 0.12))) (tstamp {uid("mout")}))',
    ]
    (PRETTY / "MP1584_Module_4pin.kicad_mod").write_text(_fp(
        "MP1584_Module_4pin",
        f"MP1584EN mini buck module, 4 through-hole pads. Row pitch {MP1584_PITCH_Y} mm is a DEFAULT - "
        "measure your module with calipers and regenerate with MP1584_PITCH_Y in tools/gen_kicad.py "
        "before ordering the PCB.",
        "mp1584 buck module",
        "\n".join(texts + lines + silk)) + "\n")


# ---------------------------------------------------------------------------
# Stock symbol loading
# ---------------------------------------------------------------------------
@lru_cache(maxsize=None)
def _lib(name):
    return parse((KISYM / f"{name}.kicad_sym").read_text())[0]


def _raw(libname, symname):
    for s in find(_lib(libname), "symbol"):
        if s[1] == symname:
            return s
    raise KeyError(f"{libname}:{symname}")


@lru_cache(maxsize=None)
def stock_symbol(lib_id):
    """Return (embedded definition, pin list) for a stock KiCad symbol, with
    any (extends ...) flattened the way KiCad caches it in a schematic."""
    libname, symname = lib_id.split(":")
    sym = _raw(libname, symname)
    ext = first(sym, "extends")
    base = _raw(libname, ext[1]) if ext else sym
    out = [Sym("symbol"), lib_id]
    for tag in ("pin_names", "pin_numbers", "in_bom", "on_board", "power", "unit_count"):
        for n in find(base, tag):
            out.append(n)
    seen = set()
    for src in (sym, base):                       # child properties win
        for p in find(src, "property"):
            if p[1] not in seen:
                seen.add(p[1])
                out.append(p)
    for sub in find(base, "symbol"):
        suffix = "_".join(sub[1].split("_")[-2:])
        out.append([Sym("symbol"), f"{symname}_{suffix}"] + list(sub[2:]))
    return out


def pins_of(defn, symname):
    res = {}
    for sub in find(defn, "symbol"):
        for p in find(sub, "pin"):
            at = first(p, "at")
            res[first(p, "number")[1]] = (float(at[1]), float(at[2]), int(float(at[3])),
                                          first(p, "name")[1])
    return res


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------
def place(px, py, angle):
    """Symbol-space (Y up) local point -> schematic offset (Y down), rotated CCW."""
    u, v = px, -py
    a = math.radians(angle)
    return (u * math.cos(a) + v * math.sin(a), -u * math.sin(a) + v * math.cos(a))


OUTWARD = {0: (-1, 0), 90: (0, 1), 180: (1, 0), 270: (0, -1)}


def sym_bbox(defn, angle):
    """Screen-space bounding box of a symbol's graphics, placed at the origin."""
    pts = []
    for sub in find(defn, "symbol"):
        for g in sub[2:]:
            if not isinstance(g, list):
                continue
            if g[0] == "rectangle":
                for tag in ("start", "end"):
                    n = first(g, tag)
                    pts.append((float(n[1]), float(n[2])))
            elif g[0] == "polyline":
                for n in find(first(g, "pts"), "xy"):
                    pts.append((float(n[1]), float(n[2])))
            elif g[0] == "circle":
                c, r = first(g, "center"), first(g, "radius")
                cx, cy, rr = float(c[1]), float(c[2]), float(r[1])
                pts += [(cx - rr, cy - rr), (cx + rr, cy + rr)]
            elif g[0] == "arc":
                for tag in ("start", "mid", "end"):
                    n = first(g, tag)
                    if n:
                        pts.append((float(n[1]), float(n[2])))
            elif g[0] == "pin":   # pins stick out past the body; keep text clear of them
                at, ln = first(g, "at"), first(g, "length")
                px, py, rot, L = float(at[1]), float(at[2]), int(float(at[3])), float(ln[1])
                pts.append((px, py))
                pts.append((px + (L if rot == 0 else -L if rot == 180 else 0),
                            py + (L if rot == 90 else -L if rot == 270 else 0)))
    if not pts:
        return (-1.27, -1.27, 1.27, 1.27)
    tp = [place(x, y, angle) for x, y in pts]
    return (min(p[0] for p in tp), min(p[1] for p in tp),
            max(p[0] for p in tp), max(p[1] for p in tp))


# ---------------------------------------------------------------------------
# Schematic
# ---------------------------------------------------------------------------
def build_schematic(custom):
    root_uuid = uid("root")
    items, libs = [], {}
    pwr_n = [0]

    def lib_def(lib_id):
        if lib_id not in libs:
            if lib_id in custom:
                d = [Sym("symbol"), lib_id] + list(custom[lib_id][2:])
                libs[lib_id] = d
            else:
                libs[lib_id] = stock_symbol(lib_id)
        return libs[lib_id]

    def emit_symbol(ref, lib_id, value, fp, x, y, angle, pin_numbers, dnp, in_bom=True):
        defn = lib_def(lib_id)
        node = [Sym("symbol"), [Sym("lib_id"), lib_id],
                [Sym("at"), Sym(f"{x}"), Sym(f"{y}"), Sym(f"{angle}")],
                [Sym("unit"), Sym("1")],
                [Sym("in_bom"), Sym("yes" if in_bom else "no")],
                [Sym("on_board"), Sym("yes" if in_bom else "no")],
                [Sym("dnp"), Sym("yes" if dnp else "no")],
                [Sym("uuid"), uid("sym", ref)]]
        # properties: keep library defaults, override Reference/Value/Footprint.
        # Reference sits above the drawn body and Value below it, so the text
        # clears both the symbol and the net labels on its pins.
        _, by0, _, by1 = sym_bbox(defn, angle)
        for p in find(defn, "property"):
            nm = p[1]
            if nm == "Reference":
                val, px, py, hide = ref, x, y + by0 - 2.0, ref.startswith("#")
            elif nm == "Value":
                val, px, py, hide = value, x, y + by1 + 2.0, ref.startswith("#")
            elif nm == "Footprint":
                val, px, py, hide = fp, x, y, True
            elif nm == "Datasheet":
                val, px, py, hide = p[2], x, y, True
            else:
                val, px, py, hide = p[2], x, y, True
            eff = [Sym("effects"), [Sym("font"), [Sym("size"), Sym("1.27"), Sym("1.27")]]]
            if hide:
                eff.append(Sym("hide"))
            node.append([Sym("property"), nm, val,
                         [Sym("at"), Sym(f"{px}"), Sym(f"{py}"), Sym("0")], eff])
        for pn in pin_numbers:
            node.append([Sym("pin"), pn, [Sym("uuid"), uid("pin", ref, pn)]])
        node.append([Sym("instances"),
                     [Sym("project"), PROJECT,
                      [Sym("path"), f"/{root_uuid}",
                       [Sym("reference"), ref], [Sym("unit"), Sym("1")]]]])
        items.append(node)

    def wire(x1, y1, x2, y2, tag):
        items.append([Sym("wire"),
                      [Sym("pts"), [Sym("xy"), Sym(f"{x1:.4f}"), Sym(f"{y1:.4f}")],
                       [Sym("xy"), Sym(f"{x2:.4f}"), Sym(f"{y2:.4f}")]],
                      [Sym("stroke"), [Sym("width"), Sym("0")], [Sym("type"), Sym("default")]],
                      [Sym("uuid"), uid("wire", tag)]])

    def label(text, x, y, rot, tag):
        # A label reads left-to-right whatever its angle; the justification is
        # what decides which side of the anchor the text lands on.  Left-hand
        # pins (label angle 180) must justify right or the text runs back over
        # the symbol's own pin names.
        just = "right" if rot in (180, 270) else "left"
        items.append([Sym("label"), text,
                      [Sym("at"), Sym(f"{x:.4f}"), Sym(f"{y:.4f}"), Sym(f"{rot}")],
                      [Sym("fields_autoplaced")],
                      [Sym("effects"), [Sym("font"), [Sym("size"), Sym("1.27"), Sym("1.27")]],
                       [Sym("justify"), Sym(just)]],
                      [Sym("uuid"), uid("lbl", tag)]])

    def power(net, x, y, tag):
        pwr_n[0] += 1
        ref = f"#PWR{pwr_n[0]:03d}"
        emit_symbol(ref, POWER_SYMS[net], net, "", x, y, 0, ["1"], False, in_bom=False)

    # --- components -------------------------------------------------------
    for c in bd.C:
        defn = lib_def(c["lib_id"])
        symname = c["lib_id"].split(":")[1]
        pt = pins_of(defn, symname)
        emit_symbol(c["ref"], c["lib_id"], c["value"], c["fp"], c["x"], c["y"], c["a"],
                    sorted(pt, key=lambda k: (len(k), k)), c["dnp"],
                    in_bom=not c["ref"].startswith("#"))
        for num, net in c["pins"].items():
            if num not in pt:
                raise SystemExit(f"{c['ref']}: pin {num} not on symbol {c['lib_id']}")
            px, py, prot, _ = pt[num]
            dx, dy = place(px, py, c["a"])
            X, Y = c["x"] + dx, c["y"] + dy
            direction = (prot + c["a"]) % 360
            ox, oy = OUTWARD[direction]
            tag = f"{c['ref']}.{num}"
            if net == "":
                items.append([Sym("no_connect"),
                              [Sym("at"), Sym(f"{X:.4f}"), Sym(f"{Y:.4f}")],
                              [Sym("uuid"), uid("nc", tag)]])
            elif net in POWER_SYMS:
                L = 3.81
                wire(X, Y, X + ox * L, Y + oy * L, tag)
                power(net, X + ox * L, Y + oy * L, tag)
            else:
                label(net, X, Y, (direction + 180) % 360, tag)

    # --- block titles and notes -------------------------------------------
    for text, x, y in bd.BLOCKS:
        items.append([Sym("text"), text,
                      [Sym("at"), Sym(f"{x}"), Sym(f"{y}"), Sym("0")],
                      [Sym("effects"), [Sym("font"), [Sym("size"), Sym("3"), Sym("3")],
                                        [Sym("thickness"), Sym("0.6")], Sym("bold")],
                       [Sym("justify"), Sym("left"), Sym("bottom")]],
                      [Sym("uuid"), uid("blk", text)]])
    for x, y, text in bd.NOTES:
        items.append([Sym("text"), text,
                      [Sym("at"), Sym(f"{x}"), Sym(f"{y}"), Sym("0")],
                      [Sym("effects"), [Sym("font"), [Sym("size"), Sym("1.4"), Sym("1.4")]],
                       [Sym("justify"), Sym("left"), Sym("bottom")]],
                      [Sym("uuid"), uid("note", text)]])

    tb = [Sym("title_block"),
          [Sym("title"), bd.SHEET["title"]],
          [Sym("date"), "2026-09-14"],
          [Sym("rev"), bd.SHEET["rev"]],
          [Sym("company"), bd.SHEET["company"]],
          [Sym("comment"), Sym("1"), bd.SHEET["comment1"]],
          [Sym("comment"), Sym("2"), bd.SHEET["comment2"]]]

    sch = [Sym("kicad_sch"),
           [Sym("version"), Sym("20230121")], [Sym("generator"), Sym("eeschema")],
           [Sym("uuid"), root_uuid],
           [Sym("paper"), bd.SHEET["paper"]],
           tb,
           [Sym("lib_symbols")] + [libs[k] for k in sorted(libs)],
           *items,
           [Sym("sheet_instances"), [Sym("path"), "/", [Sym("page"), "1"]]]]
    (OUT / f"{PROJECT}.kicad_sch").write_text(dumps(sch) + "\n")
    return len(libs)


# ---------------------------------------------------------------------------
# Project, library tables, board outline
# ---------------------------------------------------------------------------
LAYERS = [(0, "F.Cu", "signal", None), (31, "B.Cu", "signal", None),
          (32, "B.Adhes", "user", "B.Adhesive"), (33, "F.Adhes", "user", "F.Adhesive"),
          (34, "B.Paste", "user", None), (35, "F.Paste", "user", None),
          (36, "B.SilkS", "user", "B.Silkscreen"), (37, "F.SilkS", "user", "F.Silkscreen"),
          (38, "B.Mask", "user", None), (39, "F.Mask", "user", None),
          (40, "Dwgs.User", "user", "User.Drawings"), (41, "Cmts.User", "user", "User.Comments"),
          (42, "Eco1.User", "user", "User.Eco1"), (43, "Eco2.User", "user", "User.Eco2"),
          (44, "Edge.Cuts", "user", None), (45, "Margin", "user", None),
          (46, "B.CrtYd", "user", "B.Courtyard"), (47, "F.CrtYd", "user", "F.Courtyard"),
          (48, "B.Fab", "user", None), (49, "F.Fab", "user", None)]
BOARD_W = BOARD_H = 60.0
BOARD_X, BOARD_Y = 100.0, 60.0
HOLE_SQ = 40.0


def build_pcb():
    lay = "\n".join('    ({} "{}" {}{})'.format(i, n, t, ' "%s"' % a if a else "")
                    for i, n, t, a in LAYERS)
    seg = []
    corners = [(BOARD_X, BOARD_Y), (BOARD_X + BOARD_W, BOARD_Y),
               (BOARD_X + BOARD_W, BOARD_Y + BOARD_H), (BOARD_X, BOARD_Y + BOARD_H)]
    for i in range(4):
        a, b = corners[i], corners[(i + 1) % 4]
        seg.append(f'  (gr_line (start {a[0]} {a[1]}) (end {b[0]} {b[1]}) '
                   f'(stroke (width 0.1) (type default)) (layer "Edge.Cuts") (tstamp {uid("edge", i)}))')
    cx, cy = BOARD_X + BOARD_W / 2, BOARD_Y + BOARD_H / 2
    notes = [
        (cx, BOARD_Y - 4, f"CAN-BUS FOC actuator carrier - {BOARD_W:.0f} x {BOARD_H:.0f} mm, 2 layer"),
        (cx, BOARD_Y + BOARD_H + 4, "Import the netlist from the schematic, then place. "
                                    f"M3 holes go on a {HOLE_SQ:.0f} mm square."),
        (cx, BOARD_Y + BOARD_H + 8, "Bottom layer stays a continuous ground pour."),
    ]
    txt = "\n".join(
        f'  (gr_text "{t}" (at {x} {y}) (layer "Cmts.User") '
        f'(effects (font (size 1.5 1.5) (thickness 0.3))) (tstamp {uid("txt", t)}))'
        for x, y, t in notes)
    marks = []
    for i, (mx, my) in enumerate([(cx - HOLE_SQ / 2, cy - HOLE_SQ / 2), (cx + HOLE_SQ / 2, cy - HOLE_SQ / 2),
                                  (cx + HOLE_SQ / 2, cy + HOLE_SQ / 2), (cx - HOLE_SQ / 2, cy + HOLE_SQ / 2)]):
        marks.append(f'  (gr_circle (center {mx} {my}) (end {mx + 1.6} {my}) '
                     f'(stroke (width 0.1) (type default)) (fill none) (layer "Dwgs.User") (tstamp {uid("mh", i)}))')
    pcb = f"""(kicad_pcb (version 20221018) (generator pcbnew)
  (general (thickness 1.6))
  (paper "A4")
  (title_block (title "{bd.SHEET['title']}") (rev "{bd.SHEET['rev']}") (company "{bd.SHEET['company']}"))
  (layers
{lay}
  )
  (setup
    (pad_to_mask_clearance 0)
    (pcbplotparams (layerselection 0x00010fc_ffffffff) (plot_on_all_layers_selection 0x0000000_00000000)
      (disableapertmacros false) (usegerberextensions false) (usegerberattributes true)
      (usegerberadvancedattributes true) (creategerberjobfile true) (dashed_line_dash_ratio 12.000000)
      (dashed_line_gap_ratio 3.000000) (svgprecision 4) (plotframeref false) (viasonmask false)
      (mode 1) (useauxorigin false) (hpglpennumber 1) (hpglpenspeed 20) (hpglpendiameter 15.000000)
      (pdf_front_fp_property_popups true) (pdf_back_fp_property_popups true) (dxfpolygonmode true)
      (dxfimperialunits true) (dxfusepcbnewfont true) (psnegative false) (psa4output false)
      (plotreference true) (plotvalue true) (plotinvisibletext false) (sketchpadsonfab false)
      (subtractmaskfromsilk false) (outputformat 1) (mirror false) (drillshape 1) (scaleselection 1)
      (outputdirectory "gerber/"))
  )
  (net 0 "")
{chr(10).join(seg)}
{chr(10).join(marks)}
{txt}
)
"""
    (OUT / f"{PROJECT}.kicad_pcb").write_text(pcb)


def build_project_files():
    (OUT / "sym-lib-table").write_text(
        '(sym_lib_table\n  (version 7)\n'
        '  (lib (name "canfoc")(type "KiCad")(uri "${KIPRJMOD}/lib/canfoc.kicad_sym")'
        '(options "")(descr "Project symbols: INA240A1D, SimpleFOC Mini, MP1584 module"))\n)\n')
    (OUT / "fp-lib-table").write_text(
        '(fp_lib_table\n  (version 7)\n'
        '  (lib (name "canfoc")(type "KiCad")(uri "${KIPRJMOD}/lib/canfoc.pretty")'
        '(options "")(descr "Project footprints: SimpleFOC Mini socket, MP1584 module"))\n)\n')
    pro = {
        "board": {"3dviewports": [], "design_settings": {"defaults": {}, "diff_pair_dimensions": [],
                  "drc_exclusions": [], "rules": {}, "track_widths": [0.0, 0.25, 0.5, 1.0, 2.0],
                  "via_dimensions": []}, "layer_presets": [], "viewports": []},
        "boards": [], "cvpcb": {"equivalence_files": []},
        "libraries": {"pinned_footprint_libs": [], "pinned_symbol_libs": []},
        "meta": {"filename": f"{PROJECT}.kicad_pro", "version": 1},
        "net_settings": {"classes": [{"bus_width": 12, "clearance": 0.2, "diff_pair_gap": 0.25,
                                      "diff_pair_via_gap": 0.25, "diff_pair_width": 0.2, "line_style": 0,
                                      "microvia_diameter": 0.3, "microvia_drill": 0.1, "name": "Default",
                                      "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)",
                                      "track_width": 0.25, "via_diameter": 0.8, "via_drill": 0.4, "wire_width": 6},
                                     {"bus_width": 12, "clearance": 0.3, "diff_pair_gap": 0.25,
                                      "diff_pair_via_gap": 0.25, "diff_pair_width": 0.2, "line_style": 0,
                                      "microvia_diameter": 0.3, "microvia_drill": 0.1, "name": "Power",
                                      "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)",
                                      "track_width": 2.0, "via_diameter": 1.2, "via_drill": 0.6, "wire_width": 6},
                                     {"bus_width": 12, "clearance": 0.2, "diff_pair_gap": 0.2,
                                      "diff_pair_via_gap": 0.25, "diff_pair_width": 0.25, "line_style": 0,
                                      "microvia_diameter": 0.3, "microvia_drill": 0.1, "name": "CAN",
                                      "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)",
                                      "track_width": 0.3, "via_diameter": 0.8, "via_drill": 0.4, "wire_width": 6}],
                         "meta": {"version": 3},
                         "net_colors": None, "netclass_assignments": None,
                         "netclass_patterns": [{"netclass": "Power", "pattern": "VBUS"},
                                               {"netclass": "Power", "pattern": "GND"},
                                               {"netclass": "Power", "pattern": "PH_*"},
                                               {"netclass": "CAN", "pattern": "CAN?"}]},
        "pcbnew": {"last_paths": {"gencad": "", "idf": "", "netlist": "", "specctra_dsn": "", "step": "",
                                  "vrml": ""}, "page_layout_descr_file": ""},
        "schematic": {"annotate_start_num": 0, "drawing": {"default_line_thickness": 6.0,
                      "default_text_size": 50.0, "field_names": [], "intersheets_ref_show": False,
                      "label_size_ratio": 0.375, "pin_symbol_size": 25.0, "text_offset_ratio": 0.15},
                      "legacy_lib_dir": "", "legacy_lib_list": [], "meta": {"version": 1},
                      "net_format_name": "", "page_layout_descr_file": "",
                      "spice_current_sheet_as_root": False, "spice_external_command": "spice \"%I\"",
                      "spice_model_current_sheet_as_root": True, "spice_save_all_currents": False,
                      "spice_save_all_voltages": False, "subpart_first_id": 65, "subpart_id_separator": 0},
        "sheets": [[uid("root"), "Root"]], "text_variables": {},
    }
    (OUT / f"{PROJECT}.kicad_pro").write_text(json.dumps(pro, indent=2) + "\n")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    custom = build_project_symbols()
    build_footprints()
    n = build_schematic(custom)
    build_project_files()
    build_pcb()
    print(f"wrote {OUT.relative_to(ROOT)}/: {PROJECT}.kicad_sch ({len(bd.C)} symbols, {n} lib_symbols), "
          f"{PROJECT}.kicad_pcb, {PROJECT}.kicad_pro, sym-lib-table, fp-lib-table, lib/canfoc.kicad_sym, "
          f"lib/canfoc.pretty/ (2 footprints)")


if __name__ == "__main__":
    main()
