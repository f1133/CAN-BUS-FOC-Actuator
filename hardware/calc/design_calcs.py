#!/usr/bin/env python3
"""
Design-point calculations for the CAN-BUS FOC actuator driver.

Every number quoted in docs/ is derived here so it can be re-checked when a
part changes.  Run:  python3 hardware/calc/design_calcs.py
"""
import math

# ----------------------------------------------------------------------------
# Part parameters (from datasheets / invoice)
# ----------------------------------------------------------------------------
VBUS_NOM      = 24.0     # V, target bus (6S Li-ion = 25.2 V full)
VBUS_ALT      = 16.0     # V, de-rated bus recommended for 30 V FETs (4S = 16.8 V)
VDD           = 3.3      # V logic / INA240 / ADC reference

# AO3400A N-channel SOT-23 (Alpha & Omega)
FET_VDS_MAX   = 30.0     # V
FET_ID_MAX    = 5.8      # A continuous, datasheet, Tc=25C ideal
FET_RDSON_10V = 0.028    # ohm @ Vgs=10V, 25C
FET_RDSON_4V5 = 0.038    # ohm @ Vgs=4.5V, 25C
FET_RDSON_HOT = 1.5      # multiplier at Tj~100C
FET_QG_4V5    = 5.5e-9   # C total gate charge @4.5V (~9 nC @10V)
FET_CISS      = 800e-12  # F
FET_THETA_JA  = 140.0    # C/W, SOT-23 on ~1 in^2 2oz copper (typ 125-160)
FET_TJ_MAX    = 150.0

# ERJ8CWFR030V shunt
SHUNT_R       = 0.030    # ohm
SHUNT_P_MAX   = 1.0      # W

# INA240A1
INA_GAIN      = 20.0     # V/V
INA_VOUT_HEADROOM = 0.15 # V from each rail, conservative (datasheet: 0.05 typ, 0.2 max)

# ADC
ADC_BITS      = 12

# Power path
BUCK_VOUT     = 5.0
BUCK_FSW      = 1.4e6    # MP2451 / MP1584 ~1.5 MHz class
BUCK_L        = 3.3e-6   # CD43 3.3uH from invoice
BUCK_L_ISAT   = 1.0      # A
LOGIC_LOAD_A  = 0.15     # MCU 30 mA + CAN 40 mA + 2x INA240 5 mA + encoder 15 mA + LED + margin
LDO_VIN       = 5.0
LDO_VOUT      = 3.3
LDO_THETA_JA  = 60.0     # C/W SOT-223 with copper pour

# MCU / PWM
FCLK          = 170e6
PWM_F         = 20e3     # Hz (center-aligned => TIM1 counts up and down)
DEAD_TIME_S   = 400e-9

# CAN
CAN_BITRATE   = 1e6
N_JOINTS      = 3
CTRL_HZ       = 1000

def hr(t):
    print("\n" + "=" * 72 + f"\n{t}\n" + "=" * 72)

# ----------------------------------------------------------------------------
hr("1. Current sensing: INA240A1 + ERJ8CWFR030V (inline / phase)")
vref = VDD / 2
swing = VDD / 2 - INA_VOUT_HEADROOM
for label, r in (("single 30 mOhm", SHUNT_R), ("2x 30 mOhm in parallel = 15 mOhm", SHUNT_R / 2)):
    v_per_a = r * INA_GAIN
    i_pk = swing / v_per_a
    lsb_a = (VDD / (2 ** ADC_BITS)) / v_per_a
    p_at_pk = i_pk ** 2 * r
    n_shunt = 1 if r == SHUNT_R else 2
    print(f"{label:38s}: {v_per_a:.3f} V/A  -> measurable ±{i_pk:.2f} A pk "
          f"({i_pk/math.sqrt(2):.2f} A rms)  ADC LSB = {lsb_a*1000:.1f} mA  "
          f"P_shunt@pk = {p_at_pk:.2f} W of {SHUNT_P_MAX*n_shunt:.0f} W")

# ----------------------------------------------------------------------------
hr("2. MOSFET thermal / current limit (AO3400A, SOT-23)")
for vgs, rds in (("Vgs=10 V", FET_RDSON_10V), ("Vgs=4.5 V", FET_RDSON_4V5)):
    rds_hot = rds * FET_RDSON_HOT
    # allowable rise to Tj=125C from 40C ambient
    p_allow = (125 - 40) / FET_THETA_JA
    # each phase current flows through exactly one FET of the half-bridge at
    # any instant, so the average conduction power per FET = I_rms^2 * R / 2
    # (two FETs share the phase).  Add ~0.1 W switching @20 kHz.
    p_sw = 0.10
    i_rms = math.sqrt(max(p_allow - p_sw, 0) * 2 / rds_hot)
    print(f"{vgs}: Rds(on) hot = {rds_hot*1000:.0f} mOhm, P_allow/FET = {p_allow:.2f} W "
          f"-> continuous phase current ≈ {i_rms:.1f} A rms ({i_rms*math.sqrt(2):.1f} A pk)")
print(f"Datasheet Id_max {FET_ID_MAX} A is at Tc=25 C on infinite heatsink — NOT achievable in SOT-23 on FR4.")
vds_margin_24 = FET_VDS_MAX - 25.2
vds_margin_16 = FET_VDS_MAX - 16.8
print(f"Vds margin @ 6S full charge 25.2 V: {vds_margin_24:.1f} V  (ringing easily exceeds this -> AVALANCHE RISK)")
print(f"Vds margin @ 4S full charge 16.8 V: {vds_margin_16:.1f} V  (acceptable with TVS + snubber)")

# ----------------------------------------------------------------------------
hr("3. Switching loss vs gate resistor (why 120 Ohm is a fallback, not a choice)")
for rg in (10, 22, 47, 120):
    tau = rg * FET_CISS
    t_sw = 3 * tau                         # ~3 tau to complete the Miller plateau, crude
    # P_sw = 0.5 * V * I * (t_on + t_off) * f   per FET, hard switching
    for vb in (VBUS_ALT, VBUS_NOM):
        p_sw = 0.5 * vb * 3.0 * (2 * t_sw) * PWM_F
        print(f"Rg={rg:4d} Ohm  Vbus={vb:4.0f} V: t_sw≈{t_sw*1e9:5.0f} ns  P_sw/FET @3 A,{PWM_F/1e3:.0f} kHz ≈ {p_sw:.2f} W", end="   ")
    print()

# ----------------------------------------------------------------------------
hr("4. Gate-driver bootstrap capacitor")
qg_10v = 9e-9
c_boot_min = qg_10v / 0.5     # allow 0.5 V droop per cycle
print(f"Qg(10V) ≈ {qg_10v*1e9:.0f} nC -> C_boot ≥ {c_boot_min*1e9:.0f} nF; use 100 nF–1 µF X7R (1 µF 50 V in stock ✔)")

# ----------------------------------------------------------------------------
hr("5. Buck 24 V -> 5 V with CD43 3.3 µH")
for vin in (VBUS_NOM, VBUS_ALT):
    d = BUCK_VOUT / vin
    di = (vin - BUCK_VOUT) * d / (BUCK_FSW * BUCK_L)
    i_pk = LOGIC_LOAD_A + di / 2
    print(f"Vin={vin:4.1f} V D={d:.2f}: ΔI_L = {di:.2f} A pk-pk  I_L,pk @ {LOGIC_LOAD_A*1000:.0f} mA load = {i_pk:.2f} A "
          f"({'OK' if i_pk < BUCK_L_ISAT else 'EXCEEDS Isat'} vs Isat {BUCK_L_ISAT} A) -> {'CCM' if di/2 < LOGIC_LOAD_A else 'DCM'}")
print("Conclusion: 3.3 µH is sized for a ~1.4 MHz 24->5 V converter at a few hundred mA (the logic rail).")
print("            It is NOT suitable as a 24->12 V gate-drive buck at 500 kHz (ΔI > 3 A).")

hr("6. LDO AMS1117-3.3 dissipation")
for vin, label in ((LDO_VIN, "from 5 V buck"), (12.0, "from 12 V"), (VBUS_NOM, "DIRECT from 24 V bus")):
    p = (vin - LDO_VOUT) * LOGIC_LOAD_A
    dt = p * LDO_THETA_JA
    ok = "OK" if (dt < 60 and vin <= 15) else "FAIL"
    note = " (exceeds 15 V abs-max input!)" if vin > 15 else ""
    print(f"{label:22s}: P = {p:.2f} W  ΔT ≈ {dt:.0f} °C  -> {ok}{note}")

# ----------------------------------------------------------------------------
hr("7. TIM1 PWM configuration @170 MHz")
arr = FCLK / (2 * PWM_F)           # center-aligned counts up to ARR then down
res_bits = math.log2(arr)
dtg = DEAD_TIME_S * FCLK           # DTG steps of 1/170 MHz for DTG[7:5]=0xx
print(f"PWM {PWM_F/1e3:.0f} kHz center-aligned: ARR = {arr:.0f}  -> {res_bits:.1f} bits duty resolution")
print(f"Dead-time {DEAD_TIME_S*1e9:.0f} ns = {dtg:.0f} tDTS steps (fits DTG[7:5]=0xx range, ≤127 steps)")
arr40 = FCLK / (2 * 40e3)
print(f"PWM 40 kHz alternative: ARR = {arr40:.0f} -> {math.log2(arr40):.1f} bits")

# ----------------------------------------------------------------------------
hr("8. CAN bus load: SN65HVD230 @ 1 Mbps classic CAN")
def frame_bits(dlc, ext=False, stuff=1.2):
    overhead = 47 if not ext else 67   # SOF..EOF+IFS for 11-bit / 29-bit
    return (overhead + 8 * dlc) * stuff
for dlc in (8, 4):
    fb = frame_bits(dlc)
    t_frame = fb / CAN_BITRATE
    frames_per_cycle = N_JOINTS * 2      # command + feedback per joint
    load = frames_per_cycle * t_frame * CTRL_HZ
    print(f"DLC={dlc}: ≈{fb:.0f} bits ({t_frame*1e6:.0f} µs)  {frames_per_cycle} frames/cycle @ {CTRL_HZ} Hz -> bus load {load*100:.0f}%")
print("Rule of thumb: keep < 60-70 %. 8-byte frames at 1 kHz are too much for 3 joints; use 4-6 byte frames or 500 Hz feedback.")

# ----------------------------------------------------------------------------
hr("9. Board power budget @ 3.5 A rms phase current (16 V bus)")
i = 3.5
p_cond = 3 * i**2 * FET_RDSON_10V * FET_RDSON_HOT     # 3 phases, one FET conducting each
p_sw   = 6 * 0.08
p_shunt = 2 * i**2 * (SHUNT_R / 2)
p_ldo  = (LDO_VIN - LDO_VOUT) * LOGIC_LOAD_A
p_logic = VDD * LOGIC_LOAD_A
total = p_cond + p_sw + p_shunt + p_ldo + p_logic
print(f"FET conduction {p_cond:.2f} W + switching {p_sw:.2f} W + shunts {p_shunt:.2f} W + LDO {p_ldo:.2f} W + logic {p_logic:.2f} W = {total:.2f} W")
print("-> needs 2 oz copper, thermal vias under FETs, and the FETs spread over ≥ 6 cm² of pour.")
