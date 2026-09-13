#!/usr/bin/env python3
"""
Design-point calculations for the CAN-BUS FOC actuator (spin 1: SimpleFOC Mini
carrier).  Every number quoted in docs/ is derived here.
Run:  python3 hardware/calc/design_calcs.py
"""
import math

VDD = 3.3

# SimpleFOC Mini v1.0 / DRV8313 (power stage, plugged in)
MINI_VM_MIN, MINI_VM_MAX = 8.0, 24.0        # Mini README; DRV8313 itself is 60 V, the Mini's 100 uF is 35 V
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
CYCLOIDAL_RATIO, POLE_PAIRS, AS5600_READ_HZ = 15, 7, 1000

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
print(f"VM {MINI_VM_MIN:.0f}–{MINI_VM_MAX:.0f} V (6S full charge 25.2 V is inside the 35 V cap / 60 V IC ratings; stay ≤ 24 V nominal)")
for i_rms in (1.0, 1.5, 1.75, 2.5 / math.sqrt(2)):
    p = 3 * i_rms**2 * DRV8313_RDS
    print(f"  {i_rms:.2f} A rms: conduction ≈ {p:.2f} W -> ΔT ≈ {p*DRV8313_THETA_JA:.0f} °C on the Mini  "
          f"({'OK' if p*DRV8313_THETA_JA < 60 else 'hot' if p*DRV8313_THETA_JA < 85 else 'too hot'})")
print("-> plan on ~1.5 A rms continuous, 2.5 A peak.  Bolt the Mini's back to the carrier's ground pour or add airflow for more.")
print(f"Mini 3.3 V pin = DRV8313 V3P3OUT, {DRV8313_V3P3_MAX_MA} mA max: NOT enough for MCU+CAN+INA240+AS5600 (~100 mA) -> leave it unconnected; carrier has its own buck.")
print(f"Electrical power, rough (VM x I): ~{MINI_VM_MAX*DRV8313_I_PK:.0f} W peak, ~{MINI_VM_MAX*1.5*1.1:.0f} W continuous")

hr("3. Buck MP1584EN VBUS -> 3.3 V, CD43 3.3 uH, SS14")
for vin in (24.0, 16.0, 12.0):
    d = BUCK_VOUT / vin; t_on = d / BUCK_FSW; di = (vin - BUCK_VOUT) * d / (BUCK_FSW * BUCK_L); i_pk = LOGIC_LOAD_A + di / 2
    print(f"Vin {vin:4.1f} V: t_on {t_on*1e9:4.0f} ns ({'OK' if t_on > BUCK_TON_MIN*1.2 else 'near min'})  ΔI {di:.2f} A  I_L,pk {i_pk:.2f} A "
          f"({'OK' if i_pk < BUCK_L_ISAT else 'EXCEEDS Isat'})  SS14: {vin:.0f} V < {SS14_VR:.0f} V Vr, {i_pk:.2f} A < {SS14_IF:.0f} A -> OK")
print(f"FB from stock: 10k + 4.7k over 4.7k -> {0.8*(1+14.7/4.7):.2f} V.  RFREQ 100 k from the THT kit.")

hr("4. Capacitor voltage ratings on the 24 V bus")
for name, vr in (("10 uF 25 V X7R", 25), ("1 uF 50 V X7R", 50), ("100 nF 250 V X7R", 250), ("470 uF 50 V electrolytic", 50), ("Mini's 100 uF 35 V", 35)):
    print(f"{name:28s}: {25.2/vr*100:3.0f} % at 25.2 V -> {'keep OFF VBUS' if 25.2/vr > 0.8 else 'OK'}")

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

hr("8. Carrier power budget @ 1.5 A rms, 24 V")
p_sh = 2 * 1.5**2 * SHUNT_R; p_mini = 3 * 1.5**2 * DRV8313_RDS; p_lg = VDD * LOGIC_LOAD_A / 0.85
print(f"Mini {p_mini:.2f} W (on the Mini) + shunts {p_sh:.2f} W + logic incl. buck loss {p_lg:.2f} W = {p_mini+p_sh+p_lg:.2f} W -> 2-layer 1 oz is fine; 2 oz if offered")

hr("9. Spin 2 reference — discrete 6-PWM bridge with the AO3400s in the drawer")
for name, f in FETS.items():
    p_allow = (125 - 40) / f["theta_ja"]; t_sw = 3 * 22 * f["ciss"]; p_sw = 0.5 * f["vbus_full"] * 3.5 * 2 * t_sw * PWM_F
    i_rms = math.sqrt(max(p_allow - p_sw, 0) * 2 / (f["rds_10v"] * 1.5))
    print(f"{name}: Vds margin {f['vds']-f['vbus_full']:.1f} V, thermal ≈ {i_rms:.1f} A rms, gate rail ≤ {f['vgs_max']-2:.0f} V, gate current {6*f['qg_10v']*PWM_F*1000:.1f} mA")
print("Needs FD6288T + 10 V rail + 22 R + TIM1 CH1N-3N on PB13/14/15 + 2x30 mOhm per phase (±5 A).  Documented, not built.")
