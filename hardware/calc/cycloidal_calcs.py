#!/usr/bin/env python3
"""
Cycloidal reducer geometry for the actuator's joints — the ratio the rest of the
repo quotes, and whether a reducer of that ratio is drawable at a given size.

The curve math is ported from woodenCariper's Fusion 360 "CycloidalDrive"
script (MIT, 2018) — https://github.com/woodenCariper/CycloidalDrive — whose
`CycloidalReducer` class is pure `math`.  Ported here so the ratio is checked in
the repo rather than inside CAD; Fusion stays optional.

Ported: the epitrochoid and its 1st-3rd derivatives, the parallel (offset)
curve, curvature radius / max usable offset, the transmission-angle extremum,
both singularity checks, and Simpson + bisection for arc-length spacing.
Not ported: the Fusion UI, and its `pickle` of dialog state into the document.

Changed from upstream, deliberately:
  * `clearance` — upstream offsets by exactly the pin radius, so a real pair
    binds.  Clearance is added to the offset and carried into the validity
    check, where it shrinks the usable eccentricity window.
  * the transmission angle returns None on singular geometry instead of the
    plausible-looking ~89.99 deg the bare bisection yields there.
  * pins = teeth + 1 (maximum reduction) is a named constraint, not implicit.

Run:  python3 hardware/calc/cycloidal_calcs.py [--self-test] [--export-csv DIR]
"""
import argparse
import math
import sys
from dataclasses import dataclass

# ---- Spin-1 joint design point ------------------------------------------
# PROVISIONAL, like RATIO/ETA in arm_model.py: the ratio is exact by
# construction, the sizes are a starting point until the joint envelope is
# fixed.  The 40 mm pin pitch circle matches the motor's 40 mm hole square
# (docs/06), so the ring pins land on the existing bolt pattern.
RING_PINS = 16            # -> ratio 15; see RATIO below
PIN_PITCH_DIA = 40.0      # mm, circle through the ring-pin centres
PIN_DIA = 3.0             # mm, ring pins
ECCENTRICITY = 0.8        # mm, cam offset
CLEARANCE = 0.05          # mm, added to the profile offset (printed parts)
OUT_PINS = 8              # output-disc pins
OUT_PIN_DIA = 6.0         # mm
OUT_PIN_PCD = 24.0        # mm, circle through the output-pin centres

# Ratio of a maximum-reduction cycloidal: teeth / (pins - teeth) with
# pins = teeth + 1, i.e. exactly pins - 1.  Nothing to measure.
RATIO = RING_PINS - 1

MIN_TRANSMISSION_ANGLE = 30.0   # deg, below this the lobe drives badly


@dataclass(frozen=True)
class Cycloidal:
    """One max-reduction cycloidal stage.  Lengths in mm, angles in rad."""
    ring_pins: int
    pin_radius: float
    pin_pitch_radius: float
    eccentricity: float
    clearance: float = 0.0

    def __post_init__(self):
        if self.ring_pins < 2 or self.pin_radius <= 0 \
                or self.pin_pitch_radius <= 0 or self.eccentricity <= 0:
            raise ValueError("ring_pins >= 2 and positive pin/pitch/eccentricity required")

    # -- derived -----------------------------------------------------------
    @property
    def teeth(self):
        """Lobes on the disc.  Maximum reduction fixes this at pins - 1."""
        return self.ring_pins - 1

    @property
    def ratio(self):
        return self.teeth / (self.ring_pins - self.teeth)

    @property
    def offset(self):
        """Distance the lobe profile sits inside the epitrochoid."""
        return self.pin_radius + self.clearance

    # Upstream carries rm (fixed circle), rc (rolling circle), rd, d.  With
    # rm = R/N and rc = R*teeth/N those collapse to rc + rm = R (the pitch
    # radius) and (rc + rm)/rm = N (the pin count), which is what the curve
    # equations below use.  Algebraically identical; --self-test pins it down.
    @property
    def _rm(self):
        return self.pin_pitch_radius / self.ring_pins

    # -- epitrochoid, x = R cos p - e cos(N p) -----------------------------
    def fxa(self, p):
        R, e, N = self.pin_pitch_radius, self.eccentricity, self.ring_pins
        return R * math.cos(p) - e * math.cos(N * p)

    def fya(self, p):
        R, e, N = self.pin_pitch_radius, self.eccentricity, self.ring_pins
        return R * math.sin(p) - e * math.sin(N * p)

    def dfxa(self, p):
        R, e, N = self.pin_pitch_radius, self.eccentricity, self.ring_pins
        return -R * math.sin(p) + e * N * math.sin(N * p)

    def dfya(self, p):
        R, e, N = self.pin_pitch_radius, self.eccentricity, self.ring_pins
        return R * math.cos(p) - e * N * math.cos(N * p)

    def ddfxa(self, p):
        R, e, N = self.pin_pitch_radius, self.eccentricity, self.ring_pins
        return -R * math.cos(p) + e * N**2 * math.cos(N * p)

    def ddfya(self, p):
        R, e, N = self.pin_pitch_radius, self.eccentricity, self.ring_pins
        return -R * math.sin(p) + e * N**2 * math.sin(N * p)

    def dddfxa(self, p):
        R, e, N = self.pin_pitch_radius, self.eccentricity, self.ring_pins
        return R * math.sin(p) - e * N**3 * math.sin(N * p)

    def dddfya(self, p):
        R, e, N = self.pin_pitch_radius, self.eccentricity, self.ring_pins
        return -R * math.cos(p) + e * N**3 * math.cos(N * p)

    # -- parallel (offset) curve: the actual lobe profile ------------------
    def fxp(self, p):
        dxa, dya = self.dfxa(p), self.dfya(p)
        return self.fxa(p) - self.offset * dya / math.hypot(dxa, dya)

    def fyp(self, p):
        dxa, dya = self.dfxa(p), self.dfya(p)
        return self.fya(p) + self.offset * dxa / math.hypot(dxa, dya)

    def dfxp(self, p):
        # An offset curve is tangent-parallel to its base, so both components
        # scale by the same (1 + k) -- upstream writes k out twice.
        return self.dfxa(p) * (1 + self._offset_k(p))

    def dfyp(self, p):
        return self.dfya(p) * (1 + self._offset_k(p))

    def _offset_k(self, p):
        dxa, dya = self.dfxa(p), self.dfya(p)
        ddxa, ddya = self.ddfxa(p), self.ddfya(p)
        return self.offset * (dya * ddxa - dxa * ddya) / (dxa**2 + dya**2)**1.5

    def ddfxp(self, p):
        dxa, dya = self.dfxa(p), self.dfya(p)
        ddxa, ddya = self.ddfxa(p), self.ddfya(p)
        dddxa, dddya = self.dddfxa(p), self.dddfya(p)
        D, w = self.offset, self.dfxa(p)**2 + self.dfya(p)**2
        return (ddxa
                - dddya * D * w**-0.5
                - ddya * -2 * D * (dxa * ddxa + dya * ddya) * w**-1.5
                - dya * -D * ((ddxa**2 + dxa * dddxa + ddya**2 + dya * dddya) * w**-1.5
                              - 3 * (dxa * ddxa + dya * ddya)**2 * w**-2.5))

    def ddfyp(self, p):
        dxa, dya = self.dfxa(p), self.dfya(p)
        ddxa, ddya = self.ddfxa(p), self.ddfya(p)
        dddxa, dddya = self.dddfxa(p), self.dddfya(p)
        D, w = self.offset, self.dfxa(p)**2 + self.dfya(p)**2
        return (ddya
                + dddxa * D * w**-0.5
                + ddxa * -2 * D * (dxa * ddxa + dya * ddya) * w**-1.5
                + dxa * -D * ((ddxa**2 + dxa * dddxa + ddya**2 + dya * dddya) * w**-1.5
                              - 3 * (dxa * ddxa + dya * ddya)**2 * w**-2.5))

    # -- validity ----------------------------------------------------------
    def curvature_radius(self, p):
        dxa, dya = self.dfxa(p), self.dfya(p)
        ddxa, ddya = self.ddfxa(p), self.ddfya(p)
        return (dxa**2 + dya**2)**1.5 / (dxa * ddya - dya * ddxa)

    def max_offset(self):
        """Largest offset that does not make the profile self-intersect.

        The extremum of the curvature radius, from upstream's closed form.
        """
        rm = self._rm
        rc = rm * self.ratio
        rd = self.eccentricity
        inacos = (2 * rc * rd**2 - rc * rm**2 + rd**2 * rm + rm**3) / (rd * rm * (rc + 2 * rm))
        if abs(inacos) <= 1:
            return min(self.curvature_radius(rm / rc * math.pi),
                       self.curvature_radius(rm / rc * math.acos(inacos)))
        return self.curvature_radius(rm / rc * math.pi)

    def eccentricity_limit(self):
        """Eccentricity at which the epitrochoid grows cusps."""
        return self.pin_pitch_radius / self.ring_pins

    def has_singular_point(self):
        """True when the profile cannot be drawn at these numbers."""
        if self.eccentricity * self.ring_pins >= self.pin_pitch_radius:
            return True                      # epitrochoid cusps
        return self.max_offset() < self.offset   # offset curve self-intersects

    def min_transmission_angle(self):
        """Worst transmission angle over one lobe [deg], or None if singular.

        Upstream labels this the minimum pressure angle.  It falls towards zero
        as the eccentricity approaches its limit; on singular geometry the
        bisection has no bracket and returns a meaningless ~90 deg, so refuse.
        """
        if self.has_singular_point():
            return None
        half_tooth = math.pi / self.teeth
        p = _bisect(self._dangle, half_tooth, 0.0, 1e-5)
        a = self._angle(p)
        return math.degrees(a if a <= math.pi / 2 else math.pi - a)

    def _angle(self, p):
        return math.atan2(self.dfyp(p), self.dfxp(p)) - math.atan2(self.fyp(p), self.fxp(p))

    def _dangle(self, p):
        xp, yp = self.fxp(p), self.fyp(p)
        dxp, dyp = self.dfxp(p), self.dfyp(p)
        ddxp, ddyp = self.ddfxp(p), self.ddfyp(p)
        return ((dxp * ddyp - ddxp * dyp) / (dxp**2 + dyp**2)
                - (xp * dyp - dxp * yp) / (xp**2 + yp**2))

    # -- geometry out ------------------------------------------------------
    def perimeter(self, upper, lower, splits=1000):
        return _simpson(lambda p: math.hypot(self.dfxp(p), self.dfyp(p)), upper, lower, splits)

    def profile_points(self, per_tooth, arc_length=True, shift=True):
        """Lobe profile, one tooth computed then rotated — so it is periodic.

        arc_length: space points evenly along the curve (upstream's default,
        slower) rather than evenly in the parameter.
        """
        cx = self.eccentricity if shift else 0.0
        last = 2 * math.pi / self.teeth
        if arc_length:
            step = self.perimeter(last, 0.0, 1000) / per_tooth
            tol = step / per_tooth / 1e6
            ps = [0.0]
            for _ in range(per_tooth - 1):
                ps.append(_bisect(lambda p, s=ps[-1]: self.perimeter(p, s, 100) - step, last, ps[-1], tol))
        else:
            ps = [i * last / per_tooth for i in range(per_tooth)]
        return [(self.fxp(i * last + p) + cx, self.fyp(i * last + p))
                for i in range(self.teeth) for p in ps]

    def ring_pin_centres(self):
        R = self.pin_pitch_radius
        return [(R * math.cos(2 * math.pi * i / self.ring_pins),
                 R * math.sin(2 * math.pi * i / self.ring_pins))
                for i in range(self.ring_pins)]


# ---- numerics (ported) ---------------------------------------------------
def _simpson(func, upper, lower, splits):
    """Composite Simpson approximation of the integral of func."""
    splits = int(splits) + (int(splits) & 1)
    h = (upper - lower) / splits
    total = func(lower) + 4 * func(lower + h) + func(upper)
    for i in range(2, splits, 2):
        total += 2 * func(lower + i * h) + 4 * func(lower + (i + 1) * h)
    return h / 3 * total


def _bisect(func, upper, lower, tol, max_iter=100):
    """Bisection.  Upstream's: keeps the half whose ends straddle a sign change."""
    for _ in range(max_iter):
        x = (upper + lower) / 2.0
        if func(x) * func(upper) > 0.0:
            upper = x
        else:
            lower = x
        if upper - lower <= tol:
            return x
    return (upper + lower) / 2.0


def design_point():
    return Cycloidal(RING_PINS, PIN_DIA / 2, PIN_PITCH_DIA / 2, ECCENTRICITY, CLEARANCE)


def max_eccentricity(ring_pins, pin_dia, pin_pitch_dia, clearance=0.0, step=0.01):
    """Largest eccentricity (to `step`) that still yields a drawable profile."""
    best, e = None, step
    while e < pin_pitch_dia / 2:
        try:
            if not Cycloidal(ring_pins, pin_dia / 2, pin_pitch_dia / 2, e, clearance).has_singular_point():
                best = e
        except (ValueError, ZeroDivisionError):
            pass
        e += step
    return best


# ---- report --------------------------------------------------------------
def report():
    c = design_point()
    lim = c.eccentricity_limit()
    ang = c.min_transmission_angle()
    ok = not c.has_singular_point()
    print(f"ratio            x{c.ratio:g}  ({c.ring_pins} ring pins, {c.teeth} lobes) — exact: pins - 1")
    print(f"pin pitch dia    {2*c.pin_pitch_radius:.1f} mm (motor's 40 mm hole square)")
    print(f"ring pin dia     {2*c.pin_radius:.1f} mm")
    print(f"eccentricity     {c.eccentricity:.2f} mm   [{'valid' if ok else 'SINGULAR'}]  "
          f"cusp limit {lim:.2f} mm, self-intersect limit "
          f"{max_eccentricity(c.ring_pins, 2*c.pin_radius, 2*c.pin_pitch_radius, c.clearance):.2f} mm")
    print(f"clearance        {c.clearance:.2f} mm on the profile offset ({c.offset:.2f} mm total)")
    if ang is None:
        print("min transmission  — singular geometry, no valid profile")
    else:
        verdict = "OK" if ang >= MIN_TRANSMISSION_ANGLE else "LOW — drives badly"
        print(f"min transmission {ang:.1f} deg  ({verdict}, want >= {MIN_TRANSMISSION_ANGLE:.0f})")
    print(f"disc eccentric throw {2*c.eccentricity:.1f} mm total; output pins {OUT_PINS} x "
          f"{OUT_PIN_DIA:.1f} mm on {OUT_PIN_PCD:.1f} mm PCD "
          f"-> disc holes {OUT_PIN_DIA + 2*c.eccentricity:.1f} mm (pin + 2 x ecc)")
    print()
    print("eccentricity window vs ring-pin diameter (clearance "
          f"{c.clearance:.2f} mm, cusp limit {lim:.2f} mm):")
    for pd in (2.0, 3.0, 4.0, 5.0):
        m = max_eccentricity(c.ring_pins, pd, 2 * c.pin_pitch_radius, c.clearance)
        print(f"  pin dia {pd:.1f} mm -> max ecc {m:.2f} mm")
    print()
    print("transmission angle across the window:")
    for e in (0.4, 0.6, 0.8, 1.0, 1.2):
        t = Cycloidal(c.ring_pins, c.pin_radius, c.pin_pitch_radius, e, c.clearance)
        a = t.min_transmission_angle()
        print(f"  ecc {e:.1f} mm -> " + ("singular" if a is None else f"{a:5.1f} deg"))
    print(f"-> GEAR_RATIO {float(RATIO):.1f}f in firmware/include/foc_config.h, "
          f"RATIO in arm_model.py: both {RATIO}, exact by construction.")


# ---- self-test -----------------------------------------------------------
# Reference values measured by running upstream's CycloidalReducer headless, so
# a regression in the port shows up as a mismatch here.  Upstream has no
# clearance, hence clearance=0 throughout.
_REF = [
    # (label, pins, pin_r, pitch_r, ecc, ratio, max_offset, min_angle)
    ("upstream dialog defaults", 11, 0.5, 4.0, 0.2, 10.0, 1.320511264624, 54.807723616629),
    ("x15 d40 p3 ecc 0.4", 16, 1.5, 20.0, 0.4, 15.0, 5.694117647059, 71.019218222179),
    ("x15 d40 p3 ecc 0.8", 16, 1.5, 20.0, 0.8, 15.0, 4.412221429646, 49.102594166720),
    ("x15 d40 p3 ecc 1.2", 16, 1.5, 20.0, 1.2, 15.0, 1.607837510891, 12.800588921330),
]
_REF_MAX_ECC = [(2.0, 1.23), (3.0, 1.20), (4.0, 1.17), (5.0, 1.12)]
_REF_PROFILE = [(18.5000000000, 0.0000000000), (19.4064033546, 1.9151553840),
                (19.6782480369, 4.0126987251)]
_REF_FXYP = [(0.05, 18.211891418121, 1.317982515755), (0.2, 18.915658510918, 3.803690023329)]


def self_test():
    fails = []

    def check(label, got, want, tol):
        bad = got is None or abs(got - want) > tol
        print(f"  {'FAIL' if bad else 'ok  '}  {label:<44} {got!r:>22}  want {want}")
        if bad:
            fails.append(label)

    print("vs upstream CycloidalDrive.py (MIT, run headless):")
    for label, n, pr, ppr, e, ratio, maxoff, ang in _REF:
        c = Cycloidal(n, pr, ppr, e, 0.0)
        check(f"{label}: ratio", float(c.ratio), ratio, 1e-12)
        check(f"{label}: max offset", c.max_offset(), maxoff, 1e-9)
        check(f"{label}: min transmission angle", c.min_transmission_angle(), ang, 1e-6)
        if c.has_singular_point():
            fails.append(f"{label}: unexpectedly singular")
            print(f"  FAIL  {label}: expected drawable")

    # Tiny pins, so only the cusp check can bind and the two limits stay separable.
    print("\ncusp limit — x15, 40 mm pitch, 0.02 mm pins (limit 20/16 = 1.25 mm):")
    for e, want_singular in ((1.20, False), (1.24, False), (1.25, True), (1.30, True)):
        c = Cycloidal(16, 0.01, 20.0, e, 0.0)
        got = c.has_singular_point()
        bad = got != want_singular
        print(f"  {'FAIL' if bad else 'ok  '}  ecc {e} singular={got}  want {want_singular}")
        if bad:
            fails.append(f"cusp limit at ecc {e}")
        if got and c.min_transmission_angle() is not None:
            fails.append(f"singular ecc {e} returned an angle")
            print(f"  FAIL  ecc {e}: angle returned on singular geometry")

    print("\nself-intersection limit binds before the cusp limit at 3 mm pins:")
    for e, want_singular in ((1.20, False), (1.21, True), (1.24, True)):
        got = Cycloidal(16, 1.5, 20.0, e, 0.0).has_singular_point()
        bad = got != want_singular
        print(f"  {'FAIL' if bad else 'ok  '}  ecc {e} singular={got}  want {want_singular}")
        if bad:
            fails.append(f"self-intersection limit at ecc {e}")

    print("\nmax eccentricity vs ring-pin diameter (x15, 40 mm pitch):")
    for pd, want in _REF_MAX_ECC:
        check(f"pin dia {pd} mm", max_eccentricity(16, pd, 40.0), want, 5e-3)

    print("\nprofile points — x15 ecc 0.8, 4/tooth, arc-length spaced:")
    pts = Cycloidal(16, 1.5, 20.0, 0.8, 0.0).profile_points(4)
    check("point count", float(len(pts)), 60.0, 0)
    for i, (wx, wy) in enumerate(_REF_PROFILE):
        check(f"point {i} x", pts[i][0], wx, 1e-6)
        check(f"point {i} y", pts[i][1], wy, 1e-6)

    print("\nraw offset curve — x15 ecc 0.8:")
    c = Cycloidal(16, 1.5, 20.0, 0.8, 0.0)
    for p, wx, wy in _REF_FXYP:
        check(f"fxp({p})", c.fxp(p), wx, 1e-9)
        check(f"fyp({p})", c.fyp(p), wy, 1e-9)

    print(f"\n{'FAILED: ' + ', '.join(fails) if fails else 'all reference values reproduced'}")
    return 1 if fails else 0


def export_csv(directory):
    import csv
    from pathlib import Path
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    c = design_point()
    with (d / "disc_profile.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["x_mm", "y_mm"])
        w.writerows([[f"{x:.6f}", f"{y:.6f}"] for x, y in c.profile_points(20)])
    with (d / "ring_pins.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["x_mm", "y_mm", "dia_mm"])
        w.writerows([[f"{x:.6f}", f"{y:.6f}", f"{2*c.pin_radius:.3f}"] for x, y in c.ring_pin_centres()])
    print(f"wrote {d/'disc_profile.csv'} and {d/'ring_pins.csv'}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--self-test", action="store_true", help="check the port against upstream's values")
    ap.add_argument("--export-csv", metavar="DIR", help="write the disc profile and ring pins as CSV")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.export_csv:
        export_csv(a.export_csv)
        return 0
    print("=" * 72 + "\nCycloidal reducer geometry (spin 1)\n" + "=" * 72)
    report()
    return 0


if __name__ == "__main__":
    sys.exit(main())
