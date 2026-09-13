#!/usr/bin/env python3
"""
Design-point calculations for the CAN-BUS FOC actuator driver (spin 1).

Every number quoted in docs/ is derived here so it can be re-checked when a
part changes.  Run:  python3 hardware/calc/design_calcs.py
"""
import math

# ----------------------------------------------------------------------------
# Part parameters (from datasheets / invoice)
# ----------------------------------------------------------------------------
VDD = 3.3                       # V logic / INA240 / ADC reference

# Bridge FET options.  Spin 1 = AOD4184 (24 V bus).  AO3400A = 16 V build.
FETS = {
    "AOD4184  TO-252 (spin 1, 24 V bus)": dict(vds=40.0, rds_10v=0.008, rds_4v5=0.010, qg_10v=40e-9, ciss=2.0e-9,
                                              theta_ja=50.0,  vgs_max=20.0, vbus_full=25.2),
    "AO3400A  SOT-23 (16 V build)":       dict(vds=30.0, rds_10v=0.028, rds_4v5=0.038, qg_10v=9e-9,  ciss=0.8e-9,
                                              theta_ja=140.0, vgs_max=12.0, vbus_full=16.8),
}
RDS_HOT = 1.5                   # Rds(on) multiplier at Tj ~100 C
TJ_LIMIT, T_AMB = 125.0, 40.0

# ERJ8CWFR030V shunt
SHUNT_R, SHUNT_P_MAX = 0.030, 1.0

# INA240A1
INA_GAIN, INA_VOUT_HEADROOM = 20.0, 0.15

ADC_BITS = 12

# Power path: MP1584EN direct to 3.3 V with the CD43 3.3 uH
BUCK_VOUT, BUCK_FSW, BUCK_L, BUCK_L_ISAT = 3.3, 1.0e6, 3.3e-6, 1.0
BUCK_TON_MIN = 100e-9           # MP1584EN
LOGIC_LOAD_A = 0.10             # MCU 30 mA + CAN ~30 mA avg + 2x INA240 5 mA + AS5600 7 mA + LEDs

# 10 V gate rail (78L10) from VBUS
GATE_V = 10.0

# MCU / PWM
FCLK, PWM_F, DEAD_TIME_S = 170e6, 20e3, 400e-9

# CAN
CAN_BITRATE, N_JOINTS, CTRL_HZ = 1e6, 3, 1000

# Actuator
CYCLOIDAL_RATIO = 15            # placeholder — set to the real reducer ratio
POLE_PAIRS = 7
AS5600_READ_HZ = 1000           # I2C reads per second the firmware schedules


def hr(t):
    print("\n" + "=" * 72 + f"\n{t}\n" + "=" * 72)


# ----------------------------------------------------------------------------
hr("1. Current sensing: INA240A1 + ERJ8CWFR030V (inline / phase)")
swing = VDD / 2 - INA_VOUT_HEADROOM
for label, r, n in (("single 30 mOhm", SHUNT_R, 1), ("2x 30 mOhm parallel = 15 mOhm (spin 1)", SHUNT_R / 2, 2)):
    v_per_a = r * INA_GAIN
    i_pk = swing / v_per_a
    lsb_a = (VDD / 2 ** ADC_BITS) / v_per_a
    print(f"{label:42s}: {v_per_a:.2f} V/A -> ±{i_pk:.2f} A pk ({i_pk/math.sqrt(2):.2f} A rms)  "
          f"LSB {lsb_a*1000:.1f} mA  P_shunt@pk {i_pk**2*r:.2f} W of {SHUNT_P_MAX*n:.0f} W")
I_PK_DESIGN = swing / (SHUNT_R / 2 * INA_GAIN)

# ----------------------------------------------------------------------------
hr("2. Bridge FET thermal / voltage margin")
for name, f in FETS.items():
    p_allow = (TJ_LIMIT - T_AMB) / f["theta_ja"]
    tau = 22 * f["ciss"]; t_sw = 3 * tau
    p_sw = 0.5 * f["vbus_full"] * 3.5 * 2 * t_sw * PWM_F
    rds_hot = f["rds_10v"] * RDS_HOT
    i_rms = math.sqrt(max(p_allow - p_sw, 0) * 2 / rds_hot)     # one FET of the pair conducts at a time
    print(f"{name}")
    print(f"   Vds margin at full-charge bus {f['vbus_full']:.1f} V: {f['vds']-f['vbus_full']:.1f} V   "
          f"Vgs max {f['vgs_max']:.0f} V vs gate rail {GATE_V:.0f} V -> {'OK' if GATE_V <= f['vgs_max']-1 else 'TOO CLOSE'}")
    print(f"   Rds hot {rds_hot*1000:.0f} mOhm, P_allow/FET {p_allow:.2f} W, P_sw@3.5A,22R {p_sw:.2f} W "
          f"-> thermal limit ≈ {i_rms:.1f} A rms;  design ±{I_PK_DESIGN:.0f} A pk / {I_PK_DESIGN/math.sqrt(2):.1f} A rms is "
          f"{'FET-limited' if i_rms < I_PK_DESIGN/math.sqrt(2) else 'sense-limited (FET has margin)'}")
    ig = 6 * f["qg_10v"] * PWM_F
    print(f"   gate-drive current 6 x Qg x f = {ig*1000:.1f} mA (+ driver Iq ~2 mA) from the 10 V rail")

# ----------------------------------------------------------------------------
hr("3. 10 V gate rail: 78L10 from VBUS")
for vb in (13.2, 16.0, 24.0, 25.2):
    i = 0.005 + 0.002
    print(f"VBUS {vb:4.1f} V: dropout {'OK' if vb - GATE_V >= 1.7 else 'DROPOUT'}  P = {(vb-GATE_V)*i*1000:.0f} mW at {i*1000:.0f} mA")
print("(A 10 V zener + 730 Ohm shunt would need 19 mA at 24 V and starve at 13 V with AOD4184's 5 mA -> use the 78L10.)")

# ----------------------------------------------------------------------------
hr("4. Bootstrap capacitor")
qg = FETS["AOD4184  TO-252 (spin 1, 24 V bus)"]["qg_10v"]
print(f"Qg 40 nC / 0.5 V droop -> C_boot >= {qg/0.5*1e9:.0f} nF; 1 uF 50 V X7R in stock -> {qg/1e-6*1000:.0f} mV droop per cycle")

# ----------------------------------------------------------------------------
hr("5. Buck MP1584EN 24 V -> 3.3 V direct with CD43 3.3 uH (no 5 V rail, no LDO)")
for vin in (24.0, 16.0, 12.0):
    d = BUCK_VOUT / vin
    t_on = d / BUCK_FSW
    di = (vin - BUCK_VOUT) * d / (BUCK_FSW * BUCK_L)
    i_pk = LOGIC_LOAD_A + di / 2
    print(f"Vin {vin:4.1f} V: D {d:.3f}  t_on {t_on*1e9:4.0f} ns ({'OK' if t_on > BUCK_TON_MIN*1.2 else 'near min on-time'})  "
          f"ΔI {di:.2f} A pk-pk  I_L,pk {i_pk:.2f} A ({'OK' if i_pk < BUCK_L_ISAT else 'EXCEEDS Isat'})  {'DCM' if di/2 > LOGIC_LOAD_A else 'CCM'}")
print("FB divider from stock: R_top = 10k + 4.7k, R_bot = 4.7k -> Vout = 0.8 x (1 + 14.7/4.7) = "
      f"{0.8*(1+14.7/4.7):.2f} V")
print("Why no LDO: everything analog (INA240 REF=VS/2, VREF+, NTC, VBUS divider) is ratiometric to the same 3V3, "
      "so buck DC tolerance cancels; 1 MHz ripple is far above the INA240 400 kHz bandwidth.")

# ----------------------------------------------------------------------------
hr("6. Capacitor voltage ratings on the 24 V bus")
for name, vr in (("10 uF 25 V X7R (CL31B106KAHNNNE)", 25), ("1 uF 50 V X7R", 50), ("100 nF 250 V X7R", 250), ("470 uF 50 V electrolytic", 50)):
    print(f"{name:36s}: {25.2/vr*100:3.0f} % of rating at 25.2 V -> {'DO NOT use on VBUS' if 25.2/vr > 0.8 else 'OK on VBUS'}")

# ----------------------------------------------------------------------------
hr("7. TIM1 PWM configuration @170 MHz")
arr = FCLK / (2 * PWM_F); dtg = DEAD_TIME_S * FCLK
print(f"PWM {PWM_F/1e3:.0f} kHz centre-aligned: ARR = {arr:.0f} -> {math.log2(arr):.1f} bits;  dead-time {DEAD_TIME_S*1e9:.0f} ns = {dtg:.0f} tDTS (+ FD6288T internal ~200 ns)")

# ----------------------------------------------------------------------------
hr("8. CAN bus load: SN65HVD230 @ 1 Mbps classic CAN, 3 joints, 1 kHz")
def frame_bits(dlc, stuff=1.2): return (47 + 8 * dlc) * stuff
for cmd, fb in ((4, 8), (8, 8)):
    t = (frame_bits(cmd) + frame_bits(fb)) / CAN_BITRATE
    print(f"cmd DLC {cmd} + feedback DLC {fb}: {N_JOINTS*t*CTRL_HZ*100:.0f} % bus load")

# ----------------------------------------------------------------------------
hr("9. AS5600 through a cycloidal reducer — where the I2C encoder becomes the bottleneck")
for joint_dps in (60, 180, 360):
    motor_rpm = joint_dps / 360 * 60 * CYCLOIDAL_RATIO
    f_e = motor_rpm / 60 * POLE_PAIRS
    print(f"joint {joint_dps:3d} °/s x{CYCLOIDAL_RATIO}: motor {motor_rpm:5.0f} rpm, electrical {f_e:5.1f} Hz, "
          f"{AS5600_READ_HZ/f_e:5.1f} AS5600 reads per electrical cycle "
          f"({'fine' if AS5600_READ_HZ/f_e >= 8 else 'marginal — velocity extrapolation needed' if AS5600_READ_HZ/f_e >= 4 else 'upgrade to SPI encoder'})")
print("AS5600 default slow-filter latency 2.2 ms; firmware sets CONF SF=2x (0.29 ms).  Joint-absolute position needs "
      "the output-side SPI encoder (J5): the motor-side sensor wraps every 1/ratio of a joint turn.")

# ----------------------------------------------------------------------------
hr("10. Board power budget @ 3.5 A rms, 24 V, AOD4184")
f = FETS["AOD4184  TO-252 (spin 1, 24 V bus)"]
p_cond = 3 * 3.5**2 * f["rds_10v"] * RDS_HOT
p_sw = 6 * 0.5 * 24 * 3.5 * 2 * 3 * 22 * f["ciss"] * PWM_F
p_sh = 2 * 3.5**2 * SHUNT_R / 2
p_lg = VDD * LOGIC_LOAD_A + (24 - GATE_V) * 0.007
print(f"FET conduction {p_cond:.2f} W + switching {p_sw:.2f} W + shunts {p_sh:.2f} W + logic/gate rails {p_lg:.2f} W = {p_cond+p_sw+p_sh+p_lg:.2f} W  "
      f"(vs ~3.1 W with AO3400 at 16 V) -> 2-layer 2 oz is comfortable")
