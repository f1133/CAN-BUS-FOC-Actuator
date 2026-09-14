#!/usr/bin/env python3
"""
Generate the single-board build sheet from two CSV sources:

  hardware/bom/single_board_bom.csv   designator-level BOM
  hardware/wiring/netlist.csv         pin-level connections

Outputs:
  hardware/wiring/wiring_diagram.svg  standalone diagram (literal colours)
  docs/07-single-board-bom-and-wiring.md
  <out_html>                          build sheet page (theme-aware, inline SVG)

Run: python3 tools/gen_board_docs.py [out_html]
"""
import csv
import html
import sys
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOM = ROOT / "hardware" / "bom" / "single_board_bom.csv"
NET = ROOT / "hardware" / "wiring" / "netlist.csv"
SVG_OUT = ROOT / "hardware" / "wiring" / "wiring_diagram.svg"
MD_OUT = ROOT / "docs" / "07-single-board-bom-and-wiring.md"

STATUS = {
    "onhand":   ("On hand", "ok"),
    "confirm":  ("On hand · confirm count", "warn"),
    "buy":      ("Buy", "buy"),
    "optional": ("Optional", "muted"),
    "dnp":      ("DNP (site only)", "muted"),
}

# ----------------------------------------------------------------------------
# SVG wiring diagram
# ----------------------------------------------------------------------------
class Svg:
    """Tiny SVG builder. Colours are resolved through `pal` so the same layout
    renders with CSS variables (HTML) or literal hex (standalone file)."""

    def __init__(self, pal):
        self.pal = pal
        self.out = []
        self.pins = {}

    def rect(self, x, y, w, h, fill="panel", stroke="ink", sw=1, rx=3, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
                        f'fill="{self.pal[fill]}" stroke="{self.pal[stroke]}" stroke-width="{sw}"{d}/>')

    def text(self, x, y, s, size=13, anchor="start", weight="normal", mono=False, fill="ink", italic=False):
        fam = "'IBM Plex Mono', ui-monospace, Menlo, monospace" if mono else "Barlow, 'Helvetica Neue', Arial, sans-serif"
        st = " font-style=\"italic\"" if italic else ""
        self.out.append(f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}" '
                        f'font-family="{fam}" fill="{self.pal[fill]}"{st}>{html.escape(s)}</text>')

    def line(self, pts, color="ink", sw=1.5, dash=None, arrow=False):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        a = ' marker-end="url(#arrow)"' if arrow else ""
        p = " ".join(f"{x},{y}" for x, y in pts)
        self.out.append(f'<polyline points="{p}" fill="none" stroke="{self.pal[color]}" stroke-width="{sw}" '
                        f'stroke-linejoin="round" stroke-linecap="round"{d}{a}/>')

    def dot(self, x, y, color="ink"):
        self.out.append(f'<circle cx="{x}" cy="{y}" r="3" fill="{self.pal[color]}"/>')

    def block(self, key, x, y, w, h, title, sub=None, left=(), right=(), pitch=26, first=40, dash=None):
        """Box with pin stubs. `left`/`right` are lists of (pin_key, label). Pin
        coordinates land in self.pins[(key, pin_key)] at the stub's outer end."""
        self.rect(x, y, w, h, dash=dash)
        self.text(x + 10, y + 19, title, size=15, weight="700")
        if sub:
            self.text(x + 10, y + 34, sub, size=11, fill="muted")
        for i, (pk, label) in enumerate(left):
            py = y + first + i * pitch
            self.pins[(key, pk)] = (x - 12, py)
            if not label:
                continue
            self.line([(x - 12, py), (x, py)], sw=1.5)
            self.text(x + 8, py + 4, label, size=12.5, mono=True)
        for i, (pk, label) in enumerate(right):
            py = y + first + i * pitch
            self.pins[(key, pk)] = (x + w + 12, py)
            if not label:
                continue
            self.line([(x + w, py), (x + w + 12, py)], sw=1.5)
            self.text(x + w - 8, py + 4, label, size=12.5, anchor="end", mono=True)

    def resistor(self, x, y, w, label, above=True, color="ink"):
        """Small inline resistor body centred on (x..x+w, y)."""
        self.rect(x, y - 7, w, 14, fill="panel", stroke=color, rx=2)
        ty = y - 11 if above else y + 22
        self.text(x + w / 2, ty, label, size=11, anchor="middle", mono=True, fill="muted")

    def flag(self, x, y, s, color="ink", anchor="start"):
        self.text(x, y, s, size=11.5, anchor=anchor, mono=True, fill=color, weight="700")

    def render(self, w, h, title):
        body = "\n".join(self.out)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" role="img" aria-label="{html.escape(title)}" '
                f'font-family="Barlow, Arial, sans-serif">\n<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
                f'markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{self.pal["ink"]}"/></marker></defs>\n'
                f'{body}\n</svg>')


def draw(pal):
    s = Svg(pal)
    W, H = 1440, 1140
    # background is transparent; the page paints the ground

    # ---- Power column --------------------------------------------------------
    s.block("J1", 40, 70, 220, 80, "J1 12 V IN", "JST-VH 2P · from the harness", right=[("1", "1 VBUS"), ("2", "2 GND")], first=50, pitch=20)
    s.block("J13", 40, 168, 220, 80, "J13 12 V OUT", "JST-VH 2P → next joint, 5 A trace", right=[("1", "1 VBUS"), ("2", "2 GND")], first=50, pitch=20)
    s.block("PROT", 40, 266, 220, 80, "Input clamp + bulk", "D1 SMBJ15A (opt) · C3 C4 470 µF 50 V", right=[("V", "VBUS"), ("G", "GND")], first=50, pitch=20)
    s.block("J6", 40, 364, 220, 80, "J6 VM OUT", "JST-VH 2P → Mini terminal · C18", right=[("1", "1 VBUS"), ("2", "2 GND")], first=50, pitch=20)
    s.block("U7", 40, 462, 220, 124, "U7 MP1584 buck module", "on hand · set to 5.00 V · C5 C21 C23",
            right=[("IN+", "IN+  VBUS"), ("IN-", "IN−  GND"), ("OUT+", "OUT+ 5V0"), ("OUT-", "OUT− GND")], first=50, pitch=20)
    s.block("U8", 40, 604, 220, 104, "U8 AMS1117-3.3", "fixed 3V3 · C6 10 µF C7 1 µF out",
            right=[("IN", "IN  ← 5V0"), ("OUT", "OUT → 3V3"), ("GND", "GND / tab")], first=50, pitch=20)
    s.block("VDDA", 40, 726, 220, 80, "VDDA filter", "R23 0 Ω · C11 C12 C13", right=[("in", "3V3"), ("out", "VDDA")], first=50, pitch=20)
    # 5V0 loop from the module to the LDO
    (x5, y5), (x8, y8) = s.pins[("U7", "OUT+")], s.pins[("U8", "IN")]
    s.line([(x5, y5), (284, y5), (284, y8), (x8, y8)], color="accent", sw=2, dash="3 3")
    s.text(280, (y5 + y8) / 2 + 4, "5V0", size=11, anchor="end", weight="700", fill="accent")

    # VBUS rail
    rail_x = 312
    s.line([(rail_x, 82), (rail_x, 512)], color="copper", sw=2.5)
    s.text(rail_x, 66, "VBUS 12 V", size=12, anchor="middle", weight="700", fill="copper")
    for key, pk in (("J1", "1"), ("J13", "1"), ("PROT", "V"), ("J6", "1"), ("U7", "IN+")):
        x, y = s.pins[(key, pk)]
        s.line([(x, y), (rail_x, y)], color="copper", sw=2.5)
        s.dot(rail_x, y, "copper")
    # 3V3 from U8 OUT to U1 VDD and VDDA filter
    x, y = s.pins[("U8", "OUT")]
    s.line([(x, y), (336, y), (336, 128), (408, 128)], color="accent", sw=2.5)
    xv, yv = s.pins[("VDDA", "in")]
    s.line([(336, y), (336, yv), (xv, yv)], color="accent", sw=2.5)
    s.dot(336, y, "accent")
    s.text(344, 118, "3V3", size=12, weight="700", fill="accent")
    xo, yo = s.pins[("VDDA", "out")]
    s.line([(xo, yo), (360, yo), (360, 154), (408, 154)], color="accent", sw=2, dash="6 4")
    s.text(368, 172, "VDDA", size=11, weight="700", fill="accent")
    # GND flags
    for key, pk in (("J1", "2"), ("J13", "2"), ("PROT", "G"), ("J6", "2"), ("U7", "IN-"), ("U7", "OUT-"), ("U8", "GND")):
        x, y = s.pins[(key, pk)]
        s.flag(x + 4, y + 4, "GND", "muted")

    # ---- MCU ---------------------------------------------------------------------
    left = [("VDD", "VDD ×3 · VBAT ← 3V3"), ("VDDA", "VDDA/VREF+ ← VDDA"), ("VSS", "VSS ×3 · VSSA  GND"),
            ("PF0", "PF0 OSC_IN   Y1"), ("PF1", "PF1 OSC_OUT  Y1"), ("NRST", "NRST         C17"), ("PB8", "PB8 BOOT0    R1"),
            ("PA2", "PA2 VBUS_SENSE"), ("PA3", "PA3 NTC"), ("PA13", "PA13 SWDIO  J11.2"), ("PA14", "PA14 SWCLK  J11.3"),
            ("PB3", "PB3 UART_TX J12.1"), ("PB4", "PB4 UART_RX J12.2"), ("PB9", "PB9 LED2"), ("PC13", "PC13 ID0"), ("PC14", "PC14 ID1"), ("PC15", "PC15 ID2")]
    right = [("PA8", "PA8  IN1"), ("PA9", "PA9  IN2"), ("PA10", "PA10 IN3"), ("PB2", "PB2  EN"), ("PB14", "PB14 nSLEEP"),
             ("PB15", "PB15 nRESET"), ("PB12", "PB12 nFAULT ⚡"), ("_g1", ""), ("PA0", "PA0 ISENSE_A"), ("PA1", "PA1 ISENSE_B"), ("_g2", ""),
             ("PA12", "PA12 CAN_TX"), ("PA11", "PA11 CAN_RX"), ("_g3", ""), ("PB6", "PB6 SCL  J3.3"), ("PB7", "PB7 SDA  J3.4"),
             ("PA4", "PA4 CS_A J4.3"), ("PA15", "PA15 CS_B J5.3"), ("PA5", "PA5 SCK  J4/J5.4"), ("PA6", "PA6 MISO J4/J5.5"), ("PA7", "PA7 MOSI J4/J5.6")]
    right_draw = [(k, l) for k, l in right if not k.startswith("_g")]
    # draw block manually so gap rows keep their slot
    s.rect(420, 70, 270, 600)
    s.text(430, 89, "U1 STM32G431CBT6", size=15, weight="700")
    s.text(430, 104, "LQFP-48 · 170 MHz · pins by port name", size=11.5, fill="muted")
    for i, (pk, label) in enumerate(left):
        py = 128 + i * 26
        s.line([(408, py), (420, py)], sw=1.5)
        s.text(428, py + 4, label, size=12.5, mono=True)
        s.pins[("U1", pk)] = (408, py)
    for i, (pk, label) in enumerate(right):
        py = 128 + i * 26
        if pk.startswith("_g"):
            continue
        s.line([(690, py), (702, py)], sw=1.5)
        s.text(682, py + 4, label, size=12.5, anchor="end", mono=True)
        s.pins[("U1", pk)] = (702, py)

    # ---- SimpleFOC Mini ------------------------------------------------------------
    mini_left = [("3", "3  IN1"), ("5", "5  IN2"), ("7", "7  IN3"), ("9", "9  EN"), ("8", "8  nSLEEP"), ("6", "6  nRESET"),
                 ("10", "10 nFAULT"), ("14", "1·4 GND"), ("2", "2  3.3V — NC")]
    mini_right = [("OUT1", "OUT1 3"), ("OUT2", "OUT2 2"), ("OUT3", "OUT3 1")]
    s.rect(920, 70, 230, 300)
    s.text(930, 89, "U6 SimpleFOC Mini", size=15, weight="700")
    s.text(930, 104, "DRV8313 · J7 2×5 (H1) · J8 1×3 (P1)", size=11.5, fill="muted")
    for i, (pk, label) in enumerate(mini_left):
        py = 128 + i * 26
        s.line([(908, py), (920, py)], sw=1.5)
        s.text(928, py + 4, label, size=12.5, mono=True)
        s.pins[("MINI", pk)] = (908, py)
    for i, (pk, label) in enumerate(mini_right):
        py = 130 + i * 50
        s.line([(1150, py), (1162, py)], color="phase", sw=2)
        s.text(1142, py + 4, label, size=12.5, anchor="end", mono=True)
        s.pins[("MINI", pk)] = (1162, py)
    s.text(1035, 356, "VM / GND screw terminal ← wire W1 from J6", size=11.5, anchor="middle", fill="copper", weight="700")

    # MCU ↔ Mini control lines (same y on both sides)
    for mpk, upk in (("3", "PA8"), ("5", "PA9"), ("7", "PA10"), ("9", "PB2"), ("8", "PB14"), ("6", "PB15"), ("10", "PB12")):
        (x1, y1), (x2, y2) = s.pins[("U1", upk)], s.pins[("MINI", mpk)]
        if upk == "PB2":
            s.line([(x1, y1), (790, y1)], sw=1.5)
            s.resistor(790, y1, 44, "R20 0 Ω")
            s.line([(834, y1), (x2, y2)], sw=1.5)
            s.text(712, y1 - 6, "R2 10 k ↓ GND", size=11, mono=True, fill="muted")
        else:
            s.line([(x1, y1), (x2, y2)], sw=1.5, arrow=(upk != "PB12"))
            if upk == "PB12":
                s.line([(x2, y2), (x1, y1)], sw=1.5, arrow=True)
    x, y = s.pins[("MINI", "14")]
    s.flag(x - 30, y + 4, "GND", "muted", anchor="end")
    x, y = s.pins[("MINI", "2")]
    s.text(x - 4, y + 4, "leave open", size=11, anchor="end", fill="buy", weight="700")

    # ---- Shunts and motor connector ----------------------------------------------
    s.block("J2", 1300, 92, 120, 168, "J2 MOTOR · XH 3P", None, left=[("1", "1 A"), ("2", "2 B"), ("3", "3 C")], first=38, pitch=50)
    for opk, jpk, rs, fa, fb in (("OUT1", "1", "RS1", "A+", "A−"), ("OUT2", "2", "RS2", "B+", "B−")):
        (x1, y1), (x2, y2) = s.pins[("MINI", opk)], s.pins[("J2", jpk)]
        s.line([(x1, y1), (1192, y1)], color="phase", sw=2)
        s.resistor(1192, y1, 50, f"{rs} 30 mΩ", above=False, color="phase")
        s.line([(1242, y1), (x2, y2)], color="phase", sw=2)
        s.dot(1186, y1, "phase"); s.dot(1248, y1, "phase")
        s.flag(1186, y1 - 12, fa, "phase", anchor="middle")
        s.flag(1248, y1 - 12, fb, "phase", anchor="middle")
    (x1, y1), (x2, y2) = s.pins[("MINI", "OUT3")], s.pins[("J2", "3")]
    s.line([(x1, y1), (x2, y2)], color="phase", sw=2)
    s.text(1231, y1 - 8, "unsensed · Ic = −(Ia+Ib)", size=11, anchor="middle", fill="muted", italic=True)

    # ---- INA240s -------------------------------------------------------------------
    for key, y0, rs, fa, fb, c, upk, rr, xj in (("U3", 420, "RS1", "A+", "A−", "C14", "PA0", "R21", 800), ("U4", 560, "RS2", "B+", "B−", "C15", "PA1", "R22", 780)):
        s.block(key, 920, y0, 200, 112, f"{key} INA240A1 · phase {fa[0]}", f"gain 20 · 0.60 V/A · ±2.5 A · {c} at VS",
                left=[("OUT", f"OUT → {upk}"), ("VS", "VS · REF1 ← 3V3"), ("GND", "REF2 · GND")],
                right=[("IN+", "IN+"), ("IN-", "IN−"), ("_", "")], first=48, pitch=26)
        xi, yi = s.pins[(key, "IN+")]
        s.flag(xi + 4, yi + 4, f"← {fa}", "phase")
        xi, yi = s.pins[(key, "IN-")]
        s.flag(xi + 4, yi + 4, f"← {fb}", "phase")
        xv, yv = s.pins[(key, "VS")]
        s.flag(xv - 4, yv + 4, "3V3", "accent", anchor="end")
        xg, yg = s.pins[(key, "GND")]
        s.flag(xg - 4, yg + 4, "GND", "muted", anchor="end")
        (xo, yo), (xu, yu) = s.pins[(key, "OUT")], s.pins[("U1", upk)]
        s.line([(xo, yo), (xj + 60, yo)], sw=1.5)
        s.resistor(xj + 16, yo, 44, f"{rr} 0 Ω")
        s.line([(xj + 16, yo), (xj, yo), (xj, yu), (xu, yu)], sw=1.5, arrow=True)
    s.text(1010, 690, "C19 C20 1 nF DNP sites at PA0 / PA1", size=11, anchor="middle", fill="muted", italic=True)

    # ---- CAN --------------------------------------------------------------------------
    s.block("U2", 920, 740, 210, 122, "U2 SN65HVD230", "SOIC-8 · C16 at VCC · pin 5 Vref NC",
            left=[("D", "D (1) ← PA12"), ("R", "R (4) → PA11"), ("VCC", "VCC (3) 3V3"), ("RS", "RS (8) R16 → GND")],
            right=[("CANH", "CANH (7)"), ("CANL", "CANL (6)")], first=48, pitch=24)
    (xd, yd), (xt, yt) = s.pins[("U2", "D")], s.pins[("U1", "PA12")]
    s.line([(xt, yt), (732, yt), (732, yd), (xd, yd)], sw=1.5, arrow=True)
    (xr, yr), (xq, yq) = s.pins[("U2", "R")], s.pins[("U1", "PA11")]
    s.line([(xr, yr), (752, yr), (752, yq), (xq, yq)], sw=1.5, arrow=True)
    s.block("J9", 1180, 740, 120, 92, "J9 CAN IN · XH 3P", None, left=[("1", "1 CANH"), ("2", "2 CANL"), ("3", "3 GND")], first=34, pitch=20)
    s.block("J10", 1180, 842, 120, 92, "J10 CAN OUT · XH 3P", None, left=[("1", "1 CANH"), ("2", "2 CANL"), ("3", "3 GND")], first=34, pitch=20)
    xh, yh = s.pins[("U2", "CANH")]; xl, yl = s.pins[("U2", "CANL")]
    bh, bl = 1148, 1166
    s.line([(xh, yh), (bh, yh)], sw=2); s.line([(xl, yl), (bl, yl)], sw=2)
    y_top_h, y_bot_h = s.pins[("J9", "1")][1], s.pins[("J10", "1")][1]
    y_top_l, y_bot_l = s.pins[("J9", "2")][1], s.pins[("J10", "2")][1]
    s.line([(bh, y_top_h), (bh, y_bot_h)], sw=2); s.line([(bl, y_top_l), (bl, y_bot_l)], sw=2)
    s.dot(bh, yh); s.dot(bl, yl)
    for j in ("J9", "J10"):
        x1, y1 = s.pins[(j, "1")]; s.line([(bh, y1), (x1, y1)], sw=2); s.dot(bh, y1)
        x2, y2 = s.pins[(j, "2")]; s.line([(bl, y2), (x2, y2)], sw=2); s.dot(bl, y2)
        x3, y3 = s.pins[(j, "3")]; s.flag(x3 - 4, y3 + 4, "GND", "muted", anchor="end")
    s.rect(bh, 833, bl - bh, 8, fill="panel", stroke="ink", rx=2)
    s.text(bh, 952, "R15 0 Ω → R14 120 Ω across CANH/CANL — fit on the two end boards only", size=11, mono=True, fill="muted")

    # ---- Encoder connectors ------------------------------------------------------
    s.block("J3", 1180, 420, 240, 150, "J3 ENCODER + NTC", "JST-XH 5P → motor AS5600 board",
            left=[("1", "1 3V3"), ("2", "2 GND"), ("3", "3 SCL ← PB6"), ("4", "4 SDA ↔ PB7"), ("5", "5 NTC → PA3 · R3 10k↑3V3")], first=48, pitch=22)
    s.block("J4", 1180, 590, 118, 140, "J4 SPI_A", "motor side",
            left=[("1", "1 3V3"), ("2", "2 GND"), ("3", "3 CS_A PA4"), ("4", "4 SCK PA5"), ("5", "5 MISO PA6"), ("6", "6 MOSI PA7")], first=50, pitch=16)
    s.block("J5", 1302, 590, 118, 140, "J5 SPI_B", "output side",
            left=[("1", "1 3V3"), ("2", "2 GND"), ("3", "3 CS_B PA15"), ("4", "4 SCK PA5"), ("5", "5 MISO PA6"), ("6", "6 MOSI PA7")], first=50, pitch=16)

    # ---- MCU support block -----------------------------------------------------------
    rows = ["PF0/PF1 · Y1 8 MHz, C1 C2 30 pF to GND",
            "PB8 BOOT0 · R1 10 k to GND (test point)",
            "NRST · C17 100 nF to GND",
            "J11 SWD 1×4 · 3V3, PA13 SWDIO, PA14 SWCLK, GND",
            "J12 UART 1×3 · PB3 TX, PB4 RX, GND",
            "PC13/14/15 ID · R11–R13 2.2 k ↓GND · R17–R19 0 Ω ↑3V3",
            "LED1 · 3V3 → R9 2.2 k → LED1 → GND  (power)",
            "LED2 · PB9 → R10 2.2 k → LED2 → GND  (status)",
            "PA2 VBUS · R4+R5 10 k from VBUS, R6 2.2 k to GND (÷10.1)",
            "PA3 NTC · R3 10 k from 3V3, thermistor on J3.5 to GND",
            "PB6/PB7 · R7 R8 4.7 k to 3V3 — DNP if on the AS5600 board"]
    s.rect(40, 826, 370, 272, dash="5 4")
    s.text(50, 845, "U1 support nets (drawn as labels, not wires)", size=15, weight="700")
    for i, r in enumerate(rows):
        s.text(50, 872 + i * 22, r, size=12.5, mono=True)

    # ---- legend -----------------------------------------------------------------
    lx, ly = 420, 1125
    s.line([(lx, ly), (lx + 30, ly)], color="copper", sw=2.5); s.text(lx + 38, ly + 4, "VBUS 12 V", size=12)
    s.line([(lx + 130, ly), (lx + 160, ly)], color="accent", sw=2.5); s.text(lx + 168, ly + 4, "5V0 → 3V3 / VDDA", size=12)
    s.line([(lx + 300, ly), (lx + 330, ly)], color="phase", sw=2); s.text(lx + 338, ly + 4, "motor phase", size=12)
    s.line([(lx + 440, ly), (lx + 470, ly)], sw=1.5, arrow=True); s.text(lx + 478, ly + 4, "logic, arrow = direction", size=12)
    s.text(lx + 670, ly + 4, "A+ A− B+ B− : shunt Kelvin taps, IN+ on the Mini side", size=12, fill="muted")

    return s.render(W, H, "Wiring of one carrier board: DC in through the buck and the Mini feed, the MCU to the SimpleFOC Mini control header, "
                          "Mini outputs through the two 30 mΩ shunts to the motor connector with the INA240 taps, CAN transceiver and connectors, encoder ports.")


PAL_FILE = dict(panel="#FFFFFF", ink="#1B211D", muted="#5F6A63", accent="#1F7A56", copper="#B5652E", phase="#2A5FA8", buy="#A33A2E")
PAL_HTML = dict(panel="var(--panel)", ink="currentColor", muted="var(--muted)", accent="var(--accent)", copper="var(--copper)", phase="var(--phase)", buy="var(--buy)")

# ----------------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------------
def load():
    bom = [{k: (v or "") for k, v in r.items()} for r in csv.DictReader(BOM.open(encoding="utf-8"))]
    net = [{k: (v or "") for k, v in r.items()} for r in csv.DictReader(NET.open(encoding="utf-8"))]
    groups = OrderedDict()
    for r in bom:
        groups.setdefault(r["group"], []).append(r)
    blocks = OrderedDict()
    for r in net:
        blocks.setdefault(r["block"], []).append(r)
    return bom, groups, blocks


def totals(bom):
    t = {"onhand": 0, "confirm": 0, "buy": 0, "optional": 0, "dnp": 0}
    for r in bom:
        t[r["status"]] += int(r["qty"])
    return t

# ----------------------------------------------------------------------------
# Markdown
# ----------------------------------------------------------------------------
def md(bom, groups, blocks):
    t = totals(bom)
    o = ["# 07 — Single-board BOM & wiring (spin 1, SimpleFOC Mini carrier)", "",
         "Generated by `tools/gen_board_docs.py` from `hardware/bom/single_board_bom.csv` and `hardware/wiring/netlist.csv`. "
         "Edit the CSVs, not this file.", "",
         "## Wiring diagram", "", "![Wiring diagram](../hardware/wiring/wiring_diagram.svg)", "",
         "Copper = VBUS 12 V (J1 in, J13 out to the next joint), green = 5V0 → 3V3 → VDDA, blue = motor phases, black = logic. `A+ A− B+ B−` are the shunt Kelvin taps, IN+ on the Mini side.", "",
         "## Connections", ""]
    for b, rows in blocks.items():
        o += [f"### {b}", "", "| Pin | Signal | Connects to | Notes |", "|---|---|---|---|"]
        o += [f"| {r['pin']} | {r['signal']} | {r['to']} | {r['notes']} |" for r in rows]
        o.append("")
    o += ["## Bill of materials — one board", "",
          f"On hand {t['onhand']} · on hand, confirm count {t['confirm']} · **to buy {t['buy']}** · optional {t['optional']} · DNP sites {t['dnp']} (line-item quantities).", ""]
    for g, rows in groups.items():
        o += [f"### {g}", "", "| Ref | Qty | Value / part | Package | Status | Where | Notes |", "|---|---|---|---|---|---|---|"]
        for r in rows:
            val = r["value"] + (f" — {r['part']}" if r["part"] else "")
            o.append(f"| {r['ref']} | {r['qty']} | {val} | {r['package']} | {STATUS[r['status']][0]} | {r['where']} | {r['notes']} |")
        o.append("")
    o += ["## Assembly notes", "",
          "* **J7 pin 2 (Mini 3.3V-out) has no copper.** It is the DRV8313's 30 mA LDO; tying it to the carrier 3V3 parallels two regulators.",
          "* **25 V 10 µF caps (C6, C11) live on the 3V3 rail only.** 100 nF 250 V and 1 µF 50 V are the parts that go on VBUS.",
          "* **Trim U7 to 5.00 V on the bench before soldering it down**; the trimmer is hard to reach afterwards. U8 (AMS1117-3.3) then holds 3V3 fixed whatever the trimmer does.",
          "* **Shunts are Kelvin-sensed**: U3/U4 IN+/IN− traces leave from the inner edge of the RS1/RS2 pads, never from the current path. IN+ on the Mini side = positive current into the motor.",
          "* **First power-up**: R20 open, Mini unplugged, bench supply limited to 200 mA. Check 3V3, then fit the Mini, then R20.",
          "* **Mini orientation**: silkscreen the H1 pin-1 corner and the P1 OUT3/OUT2/OUT1 order — a reversed Mini puts 24 V onto logic pins.",
          "* **CAN termination R14/R15** only on the two boards at the ends of the bus.",
          "* **Node ID**: R17–R19 strap PC13/14/15 to 3V3; the 2.2 k pull-downs R11–R13 are always fitted.", ""]
    return "\n".join(o)

# ----------------------------------------------------------------------------
# HTML
# ----------------------------------------------------------------------------
CSS = """
:root{--bg:#F4F6F2;--panel:#FFFFFF;--ink:#1B211D;--muted:#5F6A63;--line:#C9D1CB;--accent:#1F7A56;--copper:#B5652E;--phase:#2A5FA8;
--buy:#A33A2E;--buy-bg:#F9E8E5;--ok:#1F7A56;--ok-bg:#E3F1EA;--warn:#8A6210;--warn-bg:#F6EFD9;--muted-bg:#ECEFEA;--row:#F8FAF7;}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#151A17;--panel:#1D2521;--ink:#E6EBE6;--muted:#9AA59E;--line:#2E3833;
--accent:#4FC08A;--copper:#E0925C;--phase:#7FAEF0;--buy:#F08A7E;--buy-bg:#3A231F;--ok:#4FC08A;--ok-bg:#1F3328;--warn:#E2B657;--warn-bg:#332B15;--muted-bg:#242D28;--row:#1A211D;}}
:root[data-theme="dark"]{--bg:#151A17;--panel:#1D2521;--ink:#E6EBE6;--muted:#9AA59E;--line:#2E3833;--accent:#4FC08A;--copper:#E0925C;--phase:#7FAEF0;
--buy:#F08A7E;--buy-bg:#3A231F;--ok:#4FC08A;--ok-bg:#1F3328;--warn:#E2B657;--warn-bg:#332B15;--muted-bg:#242D28;--row:#1A211D;}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--ink);font-family:Barlow,'Helvetica Neue',Arial,sans-serif;font-size:15px;line-height:1.5;margin:0;padding-inline:clamp(16px,4vw,48px);padding-block:32px 64px}
.wrap{max-width:1180px;margin:0 auto}
h1,h2,h3{font-family:'Barlow Condensed',Barlow,Arial,sans-serif;text-wrap:balance;margin:0}
h1{font-size:clamp(34px,5vw,52px);font-weight:700;line-height:1;letter-spacing:.005em}
h2{font-size:26px;font-weight:600;margin-top:56px;padding-top:12px;border-top:2px solid var(--ink)}
h3{font-size:18px;font-weight:600;margin-top:28px;color:var(--ink)}
.eyebrow{font-family:'IBM Plex Mono',ui-monospace,monospace;font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin-bottom:10px}
.lede{max-width:66ch;color:var(--muted);margin-top:10px}
.spec{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1px;background:var(--line);border:1px solid var(--line);margin-top:24px}
.spec div{background:var(--panel);padding:10px 12px}
.spec b{display:block;font-family:'IBM Plex Mono',ui-monospace,monospace;font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);font-weight:500}
.spec span{font-family:'Barlow Condensed',sans-serif;font-size:19px;font-weight:600;overflow-wrap:anywhere}
figure{margin:20px 0 0}
.diagram{overflow-x:auto;background:var(--panel);border:1px solid var(--line);padding:8px}
.diagram svg{display:block;min-width:960px;width:100%;height:auto;color:var(--ink)}
figcaption{font-size:14px;color:var(--muted);margin-top:8px;max-width:80ch}
.tablewrap{overflow-x:auto;margin-top:10px}
table{border-collapse:collapse;width:100%;font-size:14px;font-variant-numeric:tabular-nums}
th{font-family:'IBM Plex Mono',ui-monospace,monospace;font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);font-weight:500;text-align:left;padding:8px 10px;border-bottom:1px solid var(--ink)}
td{padding:7px 10px;border-bottom:1px solid var(--line);vertical-align:top}
tbody tr:nth-child(even) td{background:var(--row)}
td.mono,th.mono{font-family:'IBM Plex Mono',ui-monospace,monospace;font-size:13px;white-space:nowrap}
td.num{text-align:right;font-family:'IBM Plex Mono',ui-monospace,monospace}
.chip{display:inline-block;font-family:'IBM Plex Mono',ui-monospace,monospace;font-size:11px;letter-spacing:.03em;padding:2px 7px;border-radius:2px;white-space:nowrap}
.chip.ok{background:var(--ok-bg);color:var(--ok)}.chip.warn{background:var(--warn-bg);color:var(--warn)}.chip.buy{background:var(--buy-bg);color:var(--buy);font-weight:700}.chip.muted{background:var(--muted-bg);color:var(--muted)}
.totals{display:flex;flex-wrap:wrap;gap:10px 22px;margin-top:14px;font-size:14px}
.totals b{font-family:'Barlow Condensed',sans-serif;font-size:22px;font-weight:700;margin-right:4px}
.notes{max-width:80ch;padding-left:20px}
.notes li{margin:6px 0}
.notes b{color:var(--ink)}
.buylist{background:var(--panel);border-left:4px solid var(--buy);padding:12px 16px;margin-top:20px;max-width:70ch}
.buylist ul{margin:6px 0 0;padding-left:18px}
footer{margin-top:56px;font-size:12.5px;color:var(--muted);font-family:'IBM Plex Mono',ui-monospace,monospace}
@media (max-width:640px){h2{font-size:22px}.spec span{font-size:18px}}
"""


SPEC = [
    ("Electrical", [
        ("DC bus", "12 V from one shared 5 A PSU over the harness; board rated 8–26 V (DRV8313 UVLO 8 V, Mini caps 35 V)"),
        ("Power pass-through", "J1 in → J13 out on a ≥ 2 mm trace; the first joint's board carries the whole 5 A"),
        ("Power stage", "SimpleFOC Mini (DRV8313): 3-PWM + EN, internal dead time, OCP / UVLO / thermal → nFAULT"),
        ("Phase current", "2.5 A peak (driver) — at 12 V a gimbal motor is voltage-limited to (12 V/√3)/R first; ~1.5 A rms continuous on the Mini's thermal budget"),
        ("Current sense", "2 × INA240A1 inline, 30 mΩ per phase: 0.60 V/A, ±2.5 A full scale, 1.3 mA/LSB, Ic reconstructed"),
        ("PWM / loops", "20 kHz centre-aligned (12.1-bit) · current 20 kHz · velocity 4 kHz · position 1 kHz"),
        ("Logic supply", "MP1584 module (on hand) trimmed to 5.00 V → AMS1117-3.3 → fixed 3V3, immune to the module trimmer; everything analog ratiometric to 3V3"),
        ("Sensing", "VBUS ÷ 10.1 (8 mV/LSB), motor NTC (10 k, B 3950), MCU die temperature"),
    ]),
    ("Interfaces", [
        ("CAN", "SN65HVD230, classic CAN 1 Mbps, 11-bit IDs, node ID 0–7 by solder straps, 120 Ω termination by jumper on the end boards; 3 joints at 1 kHz ≈ 68 % bus load"),
        ("Motor encoder", "AS5600 on the motor (I2C, 12-bit, 1 kHz reads, CONF SF = 2×) on J3 with the winding NTC"),
        ("Joint encoder", "J5 SPI (MT6701 / AS5047P, 14-bit) on the cycloidal output — absolute joint angle at power-on"),
        ("Encoder upgrade", "J4 SPI for a motor-side MT6701 / AS5047P when speed or latency outgrows the AS5600"),
        ("Debug", "SWD (J11) · UART 115200 (J12) · status LED · SimpleFOC-library compatible pin map"),
    ]),
    ("Protection", [
        ("Hardware", "DRV8313 nFAULT → TIM1 break (outputs idle in one clock) · EN pulled low through reset · bridge-disable jumper R20"),
        ("Firmware", "|I| > 2.8 A · VBUS outside 8–16 V · NTC > 100 °C · encoder error → torque off; CAN heartbeat timeout 100 ms → brake"),
        ("Input", "keyed JST-VH, optional SMBJ15A clamp, 2 × 470 µF bulk"),
    ]),
    ("Physical", [
        ("Board", "~60 × 60 mm, 2-layer 1 oz, Lion Circuits; bottom layer ground pour; 4 × M3 on a 40 mm square + 1 under the Mini"),
        ("Dissipation", "≈ 0.5 W on the carrier; ≈ 1.35 W on the Mini at 1.5 A rms (thermal pad to the carrier pour)"),
        ("Connectors", "J1/J13/J6 JST-VH 2P · J2 motor JST-XH 3P · J9/J10 CAN JST-XH 3P · J3 JST-XH 5P · J4/J5/J11/J12 0.1\" headers · J7/J8 Mini socket"),
    ]),
]


def spec_sections():
    import arm_model as am
    e = html.escape
    o = ["<h2>Specification</h2>",
         '<p class="lede">Spin 1 as it will be ordered: one carrier per joint, three joints on one 12 V / 5 A supply and one CAN bus.</p>']
    for title, rows in SPEC:
        o += [f"<h3>{e(title)}</h3>", '<div class="tablewrap"><table><tbody>']
        o += [f'<tr><td class="mono" style="width:180px">{e(k)}</td><td>{e(v)}</td></tr>' for k, v in rows]
        o.append("</tbody></table></div>")
    o += ["<h2>What the arm gets from it</h2>",
          f'<p class="lede">Per joint, from the electrical limits: torque = Kt · Iq · ratio · η, where Iq stops at whichever comes first — the driver\'s 2.5 A or the bus voltage across the winding, (12 V / √3) / R. Cycloidal ×{am.RATIO} at {am.ETA:.0%} is a placeholder until the reducer is measured; motor rows are typical values for AS5600-equipped gimbal motors — replace with yours.</p>',
          '<div class="tablewrap"><table><thead><tr><th>Motor (typical)</th><th class="num">Kv</th><th class="num">R</th><th class="num">Iq at stall</th><th>Limited by</th>'
          '<th class="num">Motor torque</th><th class="num">Joint torque</th><th class="num">Joint speed</th><th class="num">Bus current holding</th><th class="num">AS5600 reads / el. cycle</th><th class="num">Lifts at 0.3 m</th><th class="num">Joint torque at 24 V</th></tr></thead><tbody>']
    t24 = dict(am.table(vbus=24.0))
    for name, j in am.table():
        o.append(f'<tr><td>{e(name)}</td><td class="num">{j["kv"]:.0f}</td><td class="num">{j["r"]:.1f} Ω</td><td class="num">{j["iq"]:.2f} A</td><td>{e(j["limit"])}</td>'
                 f'<td class="num">{j["t_m"]:.3f} N·m</td><td class="num"><b>{j["t_j"]:.2f} N·m</b></td><td class="num">{j["dps_j"]:.0f} °/s</td>'
                 f'<td class="num">{j["i_bus_stall"]:.2f} A</td><td class="num">{j["reads"]:.1f}</td><td class="num">{j["payload"]:.2f} kg</td><td class="num">{t24[name]["t_j"]:.2f} N·m</td></tr>')
    o.append("</tbody></table></div>")
    worst = max(3 * j["i_bus_stall"] for _, j in am.table())
    o += ['<ul class="notes">',
          f"<li><b>The 5 A supply is enough.</b> Three joints holding a load at full stall current draw at most {worst:.1f} A total with these motors — the copper loss, not the mechanical power, is what a holding arm burns.</li>",
          "<li><b>At 12 V the high-resistance gimbal motors, not the driver, set the torque.</b> A 10 Ω winding reaches only 0.7 A of the driver's 2.5 A. The board, the Mini and the sense range are unchanged at 24 V, where those same motors give twice the joint torque — that is a PSU decision, not a board respin.</li>",
          "<li><b>Speed is comfortable for arm motion.</b> 300–800 °/s at the joint through ×15; the AS5600 keeps ≥ 10 reads per electrical cycle up to ~1000 rpm motor speed, above which the low-R motor wants the J4 SPI encoder.</li>",
          "<li><b>Position at power-on comes from J5</b>, the SPI encoder on the cycloidal output; the motor-side AS5600 wraps every 1/15 of a joint turn.</li>",
          "<li><b>Payload column is the raw joint figure</b> — torque ÷ (g × 0.3 m) — before subtracting the arm's own weight; a 3-joint desktop arm in this class carries a few hundred grams at 30 cm.</li>",
          "</ul>"]
    return o


def page(bom, groups, blocks, svg_html):
    t = totals(bom)
    e = html.escape
    buy = [r for r in bom if r["status"] == "buy"]
    confirm = [r for r in bom if r["status"] == "confirm"]
    o = [f"<title>FOC Carrier Build Sheet</title>",
         '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=Barlow:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;700&display=swap">',
         f"<style>{CSS}</style>", '<div class="wrap">',
         '<div class="eyebrow">CAN-BUS FOC Actuator · spin 1 · one board, one motor</div>',
         "<h1>FOC Carrier Build Sheet</h1>",
         '<p class="lede">Everything needed to order, wire and assemble one carrier board for the SimpleFOC Mini: the wiring diagram, every connection by pin, and the designator-level bill of materials with what is on hand and what is left to buy.</p>',
         '<div class="spec">',
         '<div><b>Power stage</b><span>SimpleFOC Mini</span></div><div><b>DC bus</b><span>12 V shared PSU</span></div>',
         '<div><b>Phase current</b><span>≤ 2.5 A pk</span></div><div><b>Current sense</b><span>2 × INA240 · 30 mΩ</span></div>',
         '<div><b>MCU</b><span>STM32G431CBT6</span></div><div><b>Bus</b><span>CAN 1 Mbps</span></div><div><b>PCB</b><span>2-layer ~60×60 mm</span></div>',
         "</div>",
         *spec_sections(),
         "<h2>Wiring diagram</h2>",
         f'<figure><div class="diagram">{svg_html}</div>',
         '<figcaption>One board. Copper lines are the 12 V bus (in at J1, out to the next joint at J13), green the 5V0 → 3V3 → VDDA rails, blue the motor phases through the two shunts; black lines are logic with arrows for direction. Shunt taps are shown as net labels <code>A+ A− B+ B−</code> (IN+ on the Mini side) rather than crossing wires. Pins for the MCU are given by port name; INA240 pin numbers follow the D-package datasheet.</figcaption></figure>',
         "<h2>Connections</h2>",
         '<p class="lede">By block, in the order you will wire them: Mini socket first, then power, MCU support, sense amplifiers, CAN, connectors.</p>']
    for b, rows in blocks.items():
        o += [f"<h3>{e(b)}</h3>", '<div class="tablewrap"><table><thead><tr><th class="mono">Pin</th><th>Signal</th><th>Connects to</th><th>Notes</th></tr></thead><tbody>']
        o += [f'<tr><td class="mono">{e(r["pin"])}</td><td class="mono">{e(r["signal"])}</td><td>{e(r["to"])}</td><td>{e(r["notes"])}</td></tr>' for r in rows]
        o.append("</tbody></table></div>")
    o += ["<h2>Bill of materials</h2>",
          '<div class="totals">'
          f'<div><b>{t["onhand"] + t["confirm"]}</b> on hand</div><div><b>{t["confirm"]}</b> of those need a count check</div>'
          f'<div><b style="color:var(--buy)">{t["buy"]}</b> to buy</div><div><b>{t["optional"]}</b> optional</div><div><b>{t["dnp"]}</b> DNP sites</div></div>',
          '<div class="buylist"><strong>Still to buy for this board</strong><ul>' +
          "".join(f'<li><span class="mono">{e(r["ref"])}</span> — {e(r["value"])}{(" — " + e(r["part"])) if r["part"] else ""}' + (f' <em>({e(r["notes"])})</em>' if r["notes"] else "") + "</li>" for r in buy) +
          '</ul><div style="margin-top:8px">Count to confirm on hand: ' + ", ".join(f'<span class="mono">{e(r["ref"])}</span> {e(r["value"])}' for r in confirm) + "</div></div>"]
    for g, rows in groups.items():
        o += [f"<h3>{e(g)}</h3>", '<div class="tablewrap"><table><thead><tr><th class="mono">Ref</th><th class="num">Qty</th><th>Value / part</th><th>Package</th><th>Status</th><th>Where</th><th>Notes</th></tr></thead><tbody>']
        for r in rows:
            lab, cls = STATUS[r["status"]]
            val = e(r["value"]) + (f'<br><span style="color:var(--muted)">{e(r["part"])}</span>' if r["part"] else "")
            o.append(f'<tr><td class="mono">{e(r["ref"])}</td><td class="num">{e(r["qty"])}</td><td>{val}</td><td>{e(r["package"])}</td>'
                     f'<td><span class="chip {cls}">{lab}</span></td><td>{e(r["where"])}</td><td>{e(r["notes"])}</td></tr>')
        o.append("</tbody></table></div>")
    o += ["<h2>Assembly notes</h2>", '<ul class="notes">',
          "<li><b>J7 pin 2 (Mini 3.3V-out) gets no copper.</b> It is the DRV8313's 30 mA LDO; tying it to the carrier 3V3 parallels two regulators.</li>",
          "<li><b>25 V 10 µF caps (C6, C11) live on the 3V3 rail only.</b> The 100 nF 250 V and 1 µF 50 V parts are what goes on VBUS.</li>",
          "<li><b>Trim U7 to 5.00 V on the bench before soldering it down</b> — the trimmer is hard to reach afterwards. U8 (AMS1117-3.3) then holds 3V3 fixed whatever the trimmer does.</li>",
          "<li><b>Shunts are Kelvin-sensed.</b> U3/U4 IN+/IN− traces leave from the inner edge of the RS1/RS2 pads, never from the current path. IN+ on the Mini side means positive current flows into the motor.</li>",
          "<li><b>First power-up:</b> R20 open, Mini unplugged, bench supply limited to 200 mA. Check 3V3, fit the Mini, then close R20.</li>",
          "<li><b>Mini orientation:</b> silkscreen the H1 pin-1 corner and the P1 OUT3 / OUT2 / OUT1 order. A reversed Mini puts 24 V onto logic pins.</li>",
          "<li><b>CAN termination R14/R15</b> only on the two boards at the ends of the bus.</li>",
          "<li><b>Node ID:</b> R17–R19 strap PC13/14/15 to 3V3; the 2.2 k pull-downs R11–R13 are always fitted.</li>",
          "</ul>",
          "<footer>Generated from hardware/bom/single_board_bom.csv and hardware/wiring/netlist.csv by tools/gen_board_docs.py · f1133/CAN-BUS-FOC-Actuator</footer>",
          "</div>"]
    return "\n".join(o)


def md_spec():
    import arm_model as am
    o = ["# 08 — Board specification & arm capability (spin 1)", "",
         "Generated by `tools/gen_board_docs.py`; the arm numbers come from `hardware/calc/arm_model.py`.", ""]
    for title, rows in SPEC:
        o += [f"## {title}", "", "| | |", "|---|---|"] + [f"| {k} | {v} |" for k, v in rows] + [""]
    o += ["## What the arm gets from it", "",
          f"Torque = Kt · Iq · ratio · η with Iq = min(2.5 A, (Vbus/√3)/R). Cycloidal ×{am.RATIO} at {am.ETA:.0%} is a placeholder; motor rows are typical AS5600-gimbal values — replace with the real motor.", "",
          "| Motor (typical) | Kv | R | Iq stall | Limit | Motor N·m | Joint N·m | Joint °/s | Bus A holding | AS5600 reads/cycle | Lifts at 0.3 m | Joint N·m at 24 V |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    t24 = dict(am.table(vbus=24.0))
    for name, j in am.table():
        o.append(f"| {name} | {j['kv']:.0f} | {j['r']:.1f} Ω | {j['iq']:.2f} A | {j['limit']} | {j['t_m']:.3f} | **{j['t_j']:.2f}** | {j['dps_j']:.0f} | {j['i_bus_stall']:.2f} A | {j['reads']:.1f} | {j['payload']:.2f} kg | {t24[name]['t_j']:.2f} |")
    worst = max(3 * j["i_bus_stall"] for _, j in am.table())
    o += ["", f"* Three joints all holding at stall draw ≤ {worst:.1f} A of the 5 A PSU with these motors.",
          "* At 12 V the winding resistance, not the driver, sets torque for gimbal motors; 24 V doubles it with no board change.",
          "* AS5600 stays ≥ 10 reads per electrical cycle to ~1000 rpm; faster motors want the J4 SPI encoder.",
          "* Joint-absolute position comes from the J5 encoder on the cycloidal output.", ""]
    return "\n".join(o)


def main():
    sys.path.insert(0, str(ROOT / "hardware" / "calc"))
    bom, groups, blocks = load()
    (ROOT / "docs" / "08-board-spec-and-arm-capability.md").write_text(md_spec(), encoding="utf-8")
    SVG_OUT.write_text(draw(PAL_FILE), encoding="utf-8")
    MD_OUT.write_text(md(bom, groups, blocks), encoding="utf-8")
    out_html = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "build" / "foc-carrier-build-sheet.html"
    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_html.write_text(page(bom, groups, blocks, draw(PAL_HTML)), encoding="utf-8")
    print(f"wrote {SVG_OUT.relative_to(ROOT)}, {MD_OUT.relative_to(ROOT)}, docs/08-board-spec-and-arm-capability.md, {out_html}")


if __name__ == "__main__":
    main()
