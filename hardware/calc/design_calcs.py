#!/usr/bin/env python3
"""
Design-point calculations for the CAN-BUS FOC actuator (spin 1: SimpleFOC Mini
carrier).  Every number quoted in docs/ is derived here.
Run:  python3 hardware/calc/design_calcs.py
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import arm_model as am
import cycloidal_calcs as cyc

VDD = 3.3

# SimpleFOC Mini v1.0 / DRV8313 (power stage, plugged in)
MINI_VM_MIN, MINI_VM_MAX = 8.0, 24.0        # Mini README; DRV8313 itself is 60 V, the Mini's 100 uF is 35 V
VBUS_SYS = 12.0                              # one 12 V 5 A PSU over the CAN harness; the LDO fixes this
DRV8313_I_PK = 2.5                          # A per phase
DRV8313_RDS = 0.20                          # ohm per FET (HS+LS ~0.4 ohm typ, datasheet)
DRV8313_THETA_JA = 40.0                     # C/W, HTSSOP-28 EP on the Mini's 26x20 mm 2-layer (estimate)
DRV8313_V3P3_MAX_MA = 30                    # its LDO — not enough for the carrier

# ERJ8CWFR030V shunt + INA240A1
SHUNT_R, SHUNT_P_MAX = 0.030, 1.0
INA_GAIN, INA_VOUT_HEADROOM = 20.0, 0.15
ADC_BITS = 12

# Buck: MP1584EN direct to 3.3 V, CD43 3.3 uH, SS14 catch diode
BUCK_VOUT, BUCK_FSW, BUCK_L, BUCK_L_ISAT, BUCK_TON_MIN = 3.3, 1.0e6, 3.3e-6, 1.0, 100e-9
SS14_VR, SS14_IF = 40.0, 1.0
LOGIC_LOAD_A = 0.10                          # MCU 30 + CAN ~30 avg + INA240 5 + AS5600 7 + LEDs

# MCU / PWM
FCLK, PWM_F = 170e6, 20e3

# CAN
CAN_BITRATE, N_JOINTS, CTRL_HZ = 1e6, 3, 1000

# Actuator
CYCLOIDAL_RATIO, POLE_PAIRS, AS5600_READ_HZ = cyc.RATIO, 7, 1000

# Spin-2 discrete bridge (parts in the drawer), kept for reference
FETS = {
    "AO3400A  SOT-23 (in stock, 16 V bus)": dict(vds=30.0, rds_10v=0.028, qg_10v=9e-9, ciss=0.8e-9, theta_ja=140.0, vgs_max=12.0, vbus_full=16.8),
    "AOD4184  TO-252 (24 V option)":       dict(vds=40.0, rds_10v=0.008, qg_10v=40e-9, ciss=2.0e-9, theta_ja=50.0, vgs_max=20.0, vbus_full=25.2),
}


def hr(t): print("\n" + "=" * 72 + f"\n{t}\n" + "=" * 72)


hr("1. Current sensing: INA240A1 + ERJ8CWFR030V inline on Mini OUT1/OUT2")
swing = VDD / 2 - INA_VOUT_HEADROOM
for label, r, n in (("single 30 mOhm (spin 1)", SHUNT_R, 1), ("2x 30 mOhm parallel (spin 2, discrete bridge)", SHUNT_R / 2, 2)):
    v_per_a = r * INA_GAIN; i_pk = swing / v_per_a; lsb = (VDD / 2**ADC_BITS) / v_per_a
    print(f"{label:48s}: {v_per_a:.2f} V/A -> ±{i_pk:.2f} A pk ({i_pk/math.sqrt(2):.2f} A rms)  LSB {lsb*1000:.1f} mA  "
          f"P_shunt@pk {i_pk**2*r:.2f} W of {SHUNT_P_MAX*n:.0f} W")
print(f"DRV8313 peak is {DRV8313_I_PK} A -> the single shunt's ±2.5 A range is an exact match; INA240 saturates where the driver's OCP takes over.")

hr("2. Power stage: SimpleFOC Mini (DRV8313)")
print(f"VM {MINI_VM_MIN:.0f}–{MINI_VM_MAX:.0f} V rating; the arm runs at {VBUS_SYS:.0f} V from the shared PSU (24 V remains a board option)")
for i_rms in (1.0, 1.5, 1.75, 2.5 / math.sqrt(2)):
    p = 3 * i_rms**2 * DRV8313_RDS
    print(f"  {i_rms:.2f} A rms: conduction ≈ {p:.2f} W -> ΔT ≈ {p*DRV8313_THETA_JA:.0f} °C on the Mini  "
          f"({'OK' if p*DRV8313_THETA_JA < 60 else 'hot' if p*DRV8313_THETA_JA < 85 else 'too hot'})")
print("-> plan on ~1.5 A rms continuous, 2.5 A peak.  Bolt the Mini's back to the carrier's ground pour or add airflow for more.")
print(f"Mini 3.3 V pin = DRV8313 V3P3OUT, {DRV8313_V3P3_MAX_MA} mA max: NOT enough for MCU+CAN+INA240+AS5600 (~100 mA) -> leave it unconnected; carrier has its own buck.")
print(f"Electrical power at {VBUS_SYS:.0f} V, rough (V x I): ~{VBUS_SYS*DRV8313_I_PK:.0f} W peak, ~{VBUS_SYS*1.5*1.1:.0f} W continuous per joint")

hr("3. Logic rail: AMS1117-3.3 straight off the bus (no switcher)")
LOAD = [("STM32G431 @170 MHz, peripherals on", 0.030),
        ("SN65HVD230 average at ~68 % bus load", 0.015),
        ("INA240A1 x2", 0.005),
        ("AS5600 on the motor", 0.0065),
        ("joint SPI encoder (MT6701)", 0.015),
        ("2 LEDs through 2.2k", 0.0012),
        ("pull-ups and margin", 0.003)]
tot = sum(i for _, i in LOAD)
for name, i in LOAD:
    print(f"   {name:38s} {i*1000:5.1f} mA")
print(f"   {'3V3 load':38s} {tot*1000:5.1f} mA  -> design budget {LOGIC_LOAD_A*1000:.0f} mA")
print(f"{'Vin':>6} {'P_LDO':>7} {'dT @55C/W':>10} {'dT @80C/W':>10} {'Tj @40C amb':>12}   verdict")
for vin, load, tag in ((12.0, tot, " itemised"), (12.0, LOGIC_LOAD_A, ""), (13.2, LOGIC_LOAD_A, ""),
                      (15.0, LOGIC_LOAD_A, ""), (18.0, LOGIC_LOAD_A, ""), (24.0, LOGIC_LOAD_A, "")):
    p_ldo = (vin - 3.3) * load
    d55, d80 = p_ldo * 55.0, p_ldo * 80.0
    tj = 40 + d80
    verdict = ("OK" if tj < 100 else "hot, needs a good pour" if tj < 125
               else "OVER Tj(max) 125 C" if vin <= 18 else "OVER Tj AND over the 18 V abs-max input")
    print(f"{vin:5.1f} V {p_ldo:6.2f} W {d55:9.0f} C {d80:9.0f} C {tj:11.0f} C   "
          f"{verdict}{tag and '  (the real load)'}")
print("SOT-223 theta_JA is ~55 C/W on a generous pour and ~80 C/W on a minimal one; the tab is pin 2 (VO).")
print("-> 12 V nominal is fine, 15 V is the practical ceiling, and this build is 12 V only:")
print("   a higher bus needs a switching pre-regulator back in front of the LDO.")
print("Dropout at 100 mA is ~1.1 V, so the LDO is happy long before the DRV8313's 8 V UVLO.")
print("PSRR: ~60 dB at mains/ripple frequencies falling to ~40 dB by 20 kHz; the 2 x 470 uF bulk plus")
print("C5/C21 at the input keep PWM ripple off the rail, and VDDA still sits behind R23 + C11/C12/C13.")

hr("4. Capacitor voltage ratings on the 12 V bus (15 V ceiling)")
for name, vr in (("10 uF 25 V X7R", 25), ("1 uF 50 V X7R", 50), ("100 nF 250 V X7R", 250),
                 ("470 uF 50 V electrolytic", 50), ("Mini's 100 uF 35 V", 35)):
    print(f"{name:28s}: {15.0/vr*100:3.0f} % of rating at the 15 V ceiling -> "
          f"{'marginal' if 15.0/vr > 0.8 else 'OK'}")
print("The 10 uF 25 V parts now sit on the 12 V rail at the LDO input (C21): 48 % derating is fine, though")
print("X7R DC bias leaves roughly half the marked value - which is still plenty for an LDO input.")

hr("5. TIM1 3-PWM @170 MHz")
arr = FCLK / (2 * PWM_F)
print(f"{PWM_F/1e3:.0f} kHz centre-aligned: ARR = {arr:.0f} -> {math.log2(arr):.1f} bits.  CH1/2/3 -> IN1/2/3; dead time is inside the DRV8313, CHxN unused.")

hr("6. CAN bus load: SN65HVD230 @ 1 Mbps, 3 joints, 1 kHz")
fb = lambda dlc: (47 + 8 * dlc) * 1.2
for c, f in ((4, 8), (8, 8)):
    print(f"cmd DLC {c} + feedback DLC {f}: {N_JOINTS*(fb(c)+fb(f))/CAN_BITRATE*CTRL_HZ*100:.0f} % bus load")

hr("7. AS5600 through the cycloidal reducer")
for joint_dps in (60, 180, 360):
    rpm = joint_dps / 360 * 60 * CYCLOIDAL_RATIO; f_e = rpm / 60 * POLE_PAIRS
    print(f"joint {joint_dps:3d} °/s x{CYCLOIDAL_RATIO}: motor {rpm:5.0f} rpm, {f_e:5.1f} Hz el, {AS5600_READ_HZ/f_e:5.1f} reads/cycle "
          f"({'fine' if AS5600_READ_HZ/f_e >= 8 else 'extrapolate' if AS5600_READ_HZ/f_e >= 4 else 'SPI encoder'})")
print("AS5600 CONF SF=2x at boot (0.29 ms vs 2.2 ms).  Joint-absolute position needs the output-side SPI encoder on J5.")

hr("8. Carrier power budget @ 1.5 A rms")
p_sh = 2 * 1.5 ** 2 * SHUNT_R
p_mini = 3 * 1.5 ** 2 * DRV8313_RDS
p_ldo = (VBUS_SYS - VDD) * LOGIC_LOAD_A
p_logic = VDD * LOGIC_LOAD_A
print(f"Mini {p_mini:.2f} W (dissipated on the Mini) + shunts {p_sh:.2f} W + LDO {p_ldo:.2f} W "
      f"+ logic {p_logic:.2f} W = {p_mini + p_sh + p_ldo + p_logic:.2f} W")
print(f"The LDO is now the hottest thing on the carrier at {p_ldo:.2f} W - give U8's tab a pour and keep")
print("it away from the shunts and the INA240s.")

hr("9. Arm capability at 12 V — per joint, then the shared 5 A PSU")
print(f"Vbus {am.VBUS:.0f} V, driver {am.I_DRV_PK} A pk, cycloidal x{am.RATIO} at {am.ETA:.0%}, reach {am.REACH_M} m for the payload column")
print(f"{'motor (typical values)':38s} {'Kv':>4} {'R':>5}  {'Iq stall':>9} {'limit':>14} {'T motor':>8} {'T joint':>8} {'joint °/s':>9} {'bus A@stall':>11} {'AS5600 rd/cyc':>13} {'payload@0.3m':>12}")
tot = 0
for name, j in am.table():
    tot += j["i_bus_stall"]
    print(f"{name:38s} {j['kv']:4.0f} {j['r']:5.1f}  {j['iq']:6.2f} A  {j['limit']:>14} {j['t_m']:6.3f}   {j['t_j']:6.2f}   {j['dps_j']:7.0f}   {j['i_bus_stall']:8.2f}    {j['reads']:8.1f}      {j['payload']:6.2f} kg")
print(f"Three joints all at stall (worst case hold): sum of the bus currents above per motor type <= {am.PSU_A} A PSU -> "
      + ", ".join(f"{name.split(' ')[0]} {3*j['i_bus_stall']:.1f} A" for name, j in am.table()))
print("At 24 V the same high-R gimbal motors reach 2x the stall current -> 2x joint torque: "
      + ", ".join(f"{name.split(' ')[0]} {j24['t_j']:.2f} N·m" for (name, j24) in am.table(vbus=24.0)))
print("Motor speed >~1000 rpm (low-R rows) drops below ~4 AS5600 reads per electrical cycle -> that motor wants the J4 SPI encoder.")

hr("10. Cycloidal reducer geometry (hardware/calc/cycloidal_calcs.py)")
cyc.report()

hr("11. Spin 2 reference — discrete 6-PWM bridge with the AO3400s in the drawer")
for name, f in FETS.items():
    p_allow = (125 - 40) / f["theta_ja"]; t_sw = 3 * 22 * f["ciss"]; p_sw = 0.5 * f["vbus_full"] * 3.5 * 2 * t_sw * PWM_F
    i_rms = math.sqrt(max(p_allow - p_sw, 0) * 2 / (f["rds_10v"] * 1.5))
    print(f"{name}: Vds margin {f['vds']-f['vbus_full']:.1f} V, thermal ≈ {i_rms:.1f} A rms, gate rail ≤ {f['vgs_max']-2:.0f} V, gate current {6*f['qg_10v']*PWM_F*1000:.1f} mA")
print("Needs FD6288T + 10 V rail + 22 R + TIM1 CH1N-3N on PB13/14/15 + 2x30 mOhm per phase (±5 A).  Documented, not built.")
