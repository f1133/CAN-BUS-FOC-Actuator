"""
Joint / arm capability model for the SimpleFOC-Mini carrier at a given bus voltage.

Conventions (FOC, SimpleFOC / ODrive style):
  Kt  = 8.27 / Kv          N·m per ampere of Iq (peak-phase current)
  Vph = Vbus / sqrt(3)     max phase-voltage amplitude with SVPWM (no over-modulation)
  Iq_stall = min(driver peak, Vph / R_phase)   — at stall the only limit is I·R
  rpm_max ≈ 0.85 · Kv · Vbus                    — voltage headroom under load
  bus current at stall ≈ (3 · I_rms² · R + P_logic) / Vbus   — copper loss only
Motor rows are TYPICAL values for the AS5600-equipped gimbal motors sold with
encoders; replace with the datasheet numbers for the actual motor.
"""
import math

VBUS = 12.0          # V, single shared PSU
PSU_A = 5.0          # A, PSU rating for the whole arm
I_DRV_PK = 2.5       # A, DRV8313 / INA240 range
RATIO = 15           # cycloidal — placeholder until measured
ETA = 0.85           # cycloidal efficiency
POLE_PAIRS = 7
AS5600_HZ = 1000
P_LOGIC = 0.4        # W per board
REACH_M = 0.30       # m, for the payload example
N_JOINTS = 3

MOTORS = [
    ("2804-class gimbal (typical)",        100.0, 10.0),
    ("3506 / 4108-class gimbal (typical)",  70.0,  6.0),
    ("low-resistance outrunner (typical)", 200.0,  0.5),
]


def joint(kv, r, vbus=VBUS, ratio=RATIO, eta=ETA, i_drv=I_DRV_PK):
    kt = 8.27 / kv
    v_ph = vbus / math.sqrt(3)
    iq = min(i_drv, v_ph / r)
    limit = "driver 2.5 A" if iq >= i_drv - 1e-9 else "voltage (V/R)"
    t_m = kt * iq
    t_j = t_m * ratio * eta
    rpm_m = 0.85 * kv * vbus
    dps_j = rpm_m / ratio * 6.0
    i_rms = iq / math.sqrt(2)
    i_bus_stall = (3 * i_rms ** 2 * r + P_LOGIC) / vbus
    f_el = rpm_m / 60.0 * POLE_PAIRS
    reads = AS5600_HZ / f_el
    payload = t_j / (9.81 * REACH_M)
    return dict(kv=kv, r=r, kt=kt, iq=iq, limit=limit, t_m=t_m, t_j=t_j, rpm_m=rpm_m, dps_j=dps_j,
                i_bus_stall=i_bus_stall, f_el=f_el, reads=reads, payload=payload)


def table(vbus=VBUS):
    return [(name, joint(kv, r, vbus=vbus)) for name, kv, r in MOTORS]
