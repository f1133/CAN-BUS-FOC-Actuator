# 01 — Parts analysis & sufficiency for 3 drivers

Source material analysed:

| File | What it is |
|---|---|
| `invoice_3680169.pdf` | Robu.in tax invoice INV2627/228307 (05-Sep-2026): the active/passive parts order |
| `order-ST030926127752-export.xlsx` | Connector / NTC / copper-clad order (JST-XH, JST-VH, MF52E103, headers) |
| `SimpleFOCMini-1.0.zip` | Reference design: DRV8313 (integrated 2.5 A FETs), 8–24 V, 26×20 mm, EasyEDA + Altium + Gerbers |
| `LCSampleGerber.zip` | Lion Circuits (Bengaluru) 2-layer sample Gerber — the target fab's file naming and units (imperial, `TOP.GTL/BOTTOM.GBL/OUTLINE.GKO/DRILL.drl`) |
| user-listed | AO3400 N-FET, ERJ8CWFR030V 30 mΩ shunt, STM32G431CBT6 |

Spin-1 decisions (24 V bus with AOD4184, no 5 V rail, AS5600 motors, 2-layer,
cycloidal actuator, SPI for a second encoder) are recorded in
[06-spin1-decisions.md](06-spin1-decisions.md). All numbers below come from
`hardware/calc/design_calcs.py`; the sufficiency table from
`tools/check_bom.py --boards 3`.

---

## 1. What the parts tell us about the intended design

* **INA240A1 ×8 + 30 mΩ 1206 shunts** → **inline (phase) current sensing**.
  INA240 exists for exactly this: −4…+80 V common-mode with PWM-edge
  rejection, so the shunt sits in the motor phase and can be sampled at any
  point of the PWM cycle. The SimpleFOCMini reference has no current sense at
  all.
* **8 INA240 for 3 boards = 2 per board (+2 spare)** → **2-shunt FOC**
  (Ia, Ib measured; Ic = −Ia−Ib). A 3rd shunt is not possible on three boards.
* **SN65HVD230 ×4 + 120 Ω ×100** → 3.3 V classic CAN, 3 nodes + spare.
* **CD43 3.3 µH ×4** → one buck per board. It is sized for a ~1 MHz 24→3.3 V
  (or 5 V) converter at ≤ 300 mA; not for a 24→12 V gate-drive buck.
* **AMS1117-3.3 ×5** → the invoice's plan was buck→5 V→LDO. Spin 1 runs the
  buck straight to 3.3 V and leaves the AMS1117 unused (nothing on the board
  needs 5 V; everything analog is ratiometric to the same rail).
* **8 MHz crystal ×6 + 30 pF ×12** → HSE (HSI16 ±1 % is marginal for 1 Mbps
  CAN). 30 pF is right for the crystal's 20 pF CL.
* **470 µF 50 V ×6** → two bulk DC-link caps per board, 50 % of rating at
  25.2 V.
* **10 µF 25 V ×14** → **3.3 V rail only.** They are at 101 % of rating on a
  full 6S bus. The 100 nF parts are 250 V and the 1 µF are 50 V — those go on
  VBUS.
* **AO3481 P-FET ×2** → reverse-polarity; dropped (JST-VH is keyed).
* **MF52E103 NTC ×5** → motor winding temperature, one per board, on the
  encoder cable.
* **JST-VH 2-pin (10 A)** → DC in. **JST-XH 3-pin** → phases. **JST-XH
  5-pin** → AS5600 + NTC.
* **Single-sided copper clad ×4** → not usable for this board (§5).

## 2. Capability of the board as specified

### 2.1 Power stage

| | AOD4184 (spin 1) | AO3400A (16 V build) |
|---|---|---|
| Package | TO-252, 40 V, 8 mΩ @ 10 V, Qg ≈ 40 nC | SOT-23, 30 V, 28 mΩ @ 10 V, Qg ≈ 9 nC |
| Vds margin at full-charge bus | 14.8 V @ 25.2 V (6S) | 13.2 V @ 16.8 V (4S) — only 4.8 V at 25.2 V → **not for 24 V** |
| Vgs abs-max vs 10 V gate rail | 20 V — fine | 12 V — 10 V rail is mandatory, 12 V would be at the limit |
| Thermal continuous phase current | ≈ 15 A rms (not the limit) | ≈ 5 A rms on 2 oz copper; datasheet 5.8 A is a Tc = 25 °C number |
| Gate-drive current from 10 V rail | 4.8 mA + driver Iq | 1.1 mA + driver Iq |
| Hand soldering | easy, proper thermal tab | easy, poor thermal path |

The AO3400 was the single bottleneck keeping the bus at 16 V. Swapping to a
TO-252 40 V part unlocks 24 V and removes the FET from the thermal budget for
~₹10 a piece. Same gate driver, same 10 V rail, same firmware (build flag).

### 2.2 Current sense — INA240A1 (20 V/V) + ERJ8CWFR030V (30 mΩ, 1 W)

INA240 at 3.3 V with REF = VS/2 gives ±1.5 V usable swing:

| Shunt | Sensitivity | Range | ADC LSB | Shunt power at range |
|---|---|---|---|---|
| single 30 mΩ | 0.60 V/A | ±2.5 A pk (1.77 A rms) | 1.3 mA | 0.19 W of 1 W |
| **2 × 30 mΩ ‖ = 15 mΩ (spin 1)** | 0.30 V/A | **±5.0 A pk (3.54 A rms)** | 2.7 mA | 0.38 W of 2 W |

"Max spec" = the parallel pair: **12 shunts for 3 boards.**

### 2.3 Spin-1 design point

| Parameter | Value | Set by |
|---|---|---|
| DC bus | **24 V** (10–28 V) | AOD4184; MP1584 28 V; 78L10 30 V; caps 50 V |
| Peak phase current | **±5 A** | INA240 + 15 mΩ |
| Continuous phase current | **3.5 A rms** | sense range; JST-XH phase pins (3 A) are the next limit |
| Board dissipation at 3.5 A rms | ≈ 2.6 W | 2-layer 2 oz is comfortable |
| PWM | 20 kHz centre-aligned, 12.1-bit | TIM1 @ 170 MHz |
| Dead time | 400 ns + FD6288T internal ~200 ns | |
| Peak electrical power | ≈ 120 W; ~85 W continuous | a real arm joint through a cycloidal |

### 2.4 Communication — SN65HVD230 (1 Mbps classic CAN)

* 3 joints, 1 kHz: 4-byte command + 8-byte feedback = **68 % bus load**;
  8 + 8 = 80 %. Protocol (doc 05) keeps commands at 4 bytes.
* Footprint is made pin-compatible with **TCAN332** (3.3 V, 5 Mbps CAN-FD) for
  a later upgrade: pin 5 NC, pin 8 to GND through 0 Ω (RS on the HVD230,
  STB on the TCAN).

### 2.5 Logic supply — MP1584EN direct to 3.3 V

24→3.3 V at ~1 MHz with the 3.3 µH: t_on = 137 ns (min 100 ns), ripple
0.86 A pk-pk, inductor peak 0.53 A (Isat 1 A), DCM at the ~100 mA logic load.
Feedback from stock: 10 k + 4.7 k over 4.7 k → 3.30 V. No 5 V rail, no LDO:
INA240 REF, VREF+, the NTC divider and the VBUS divider are all ratiometric to
the same rail, and 1 MHz ripple is well above the INA240's 400 kHz bandwidth.

### 2.6 Connectors

* J1 JST-VH 2-pin — DC in, 10 A. ✔
* J2 JST-XH 3-pin — phases, ~3 A/pin. Fine for spin 1 at 3.5 A rms bursts;
  the bottleneck upgrade is a JST-VH 3-pin or 5.08 mm screw terminal.
* J3 JST-XH 5-pin — **3V3, GND, SCL, SDA, NTC**: one cable to the motor's
  AS5600 board and the winding thermistor.
* J4 / J5 1×6 headers (cut from the female strip) — **SPI_A** (motor-side
  upgrade: MT6701 SSI or AS5047P) and **SPI_B** (output-side absolute encoder
  through the cycloidal). Shared SCK/MISO/MOSI, separate CS (PA4 / PA15).

## 3. Sufficiency for 3 boards

`python3 tools/check_bom.py --boards 3`:

| Part | per board | ×3 | on hand | Status |
|---|---|---|---|---|
| STM32G431CBT6 | 1 | 3 | ? | buy 4 |
| SN65HVD230DR | 1 | 3 | 4 | OK |
| INA240A1DR | 2 | 6 | 8 | OK |
| CD43 3.3 µH | 1 | 3 | 4 | OK |
| 8 MHz SMD crystal | 1 | 3 | 6 | OK |
| 30 pF | 2 | 6 | 12 | OK |
| 470 µF 50 V | 2 | 6 | 6 | OK, zero spare |
| 10 µF 25 V (3V3 rail only) | 2 | 6 | 14 | OK |
| 100 nF 250 V | 14 | 42 | 50 | OK |
| 1 µF 50 V | 6 | 18 | 22 | OK |
| 10 k | 7 | 21 | 30 | OK |
| 4.7 k | 4 | 12 | 16 | OK |
| 2.2 k | 6 | 18 | 100 | OK |
| 120 Ω | 1 | 3 | 100 | OK |
| 0 Ω | 5 | 15 | 44 | OK |
| Red LED | 2 | 6 | 9 | OK |
| ERJ8CWFR030V | 4 | 12 | ? | buy 15 |
| NTC MF52E103 | 1 | 3 | 5 | OK |
| JST-VH 2P / XH 3P / XH 5P | 1 each | 3 | 10 / 10 / 5 | OK |
| 1×40 header | 19 pos | 57 | 160 | OK |
| AMS1117-3.3, AO3481, HC49/U crystals, copper clad | 0 | — | — | not used |

## 4. What to buy (blockers)

| # | Part | Qty (3 boards + spares) | Why |
|---|---|---|---|
| 1 | STM32G431CBT6 | 4 | MCU |
| 2 | **AOD4184** TO-252 | 24 | bridge FETs for 24 V (AO3400 = 16 V build) |
| 3 | ERJ8CWFR030V | 15 | 4/board |
| 4 | **FD6288T** (or EG2133) | 4 | 3-phase bootstrap gate driver, 3.3 V logic, integrated bootstrap diodes + shoot-through lockout |
| 5 | **78L10** SOT-89/TO-92 | 4 | 10 V gate rail, ~7 mA. A zener shunt needs 19 mA at 24 V and starves at 13 V — use the regulator |
| 6 | 22 Ω 1206 | 20 | gate resistors (120 Ω from stock costs 0.3–0.4 W/FET switching loss) |
| 7 | **MP1584EN** | 4 | 24→3.3 V buck |
| 8 | SS34 | 4 | its catch diode |
| 9 | 100 kΩ 1206 | 4 | its fsw-set resistor (~1 MHz) |
| 10 | SMBJ26A | 4 | VBUS hot-plug clamp (SMBJ18A for a 16 V build) |
| 11 | 2-layer PCB, 2 oz, Lion Circuits | 5 | |

Nothing else. Encoders come with the motors; magnets are on them.

## 5. The copper-clad boards are not usable for this design

LQFP-48 escape routing, three half-bridges, Kelvin-connected 15 mΩ shunts and a
1 Mbps CAN pair need two copper layers with a continuous ground pour. A 2-layer
board from Lion Circuits is fine at 3.5 A rms / 24 V (their 6 mil capability
covers the 0.5 mm pitch; ask for 2 oz). Use the copper clad for a test jig.

## 6. Reference-design comparison (SimpleFOCMini)

| | SimpleFOCMini v1.0 | This design |
|---|---|---|
| Driver | DRV8313, integrated FETs | 6 × AOD4184 + FD6288T |
| Current | 2.5 A/phase, no sensing | ±5 A pk / 3.5 A rms, 2-shunt inline INA240 |
| MCU | none (external Arduino) | on-board STM32G431 |
| Interface | 3× PWM + EN pins | CAN 1 Mbps, node-ID straps |
| Encoder | external | AS5600 (I2C) + two SPI ports |
| Size / layers | 26 × 20 mm, 2-layer | ~60 × 60 mm, 2-layer 2 oz |
| Protection | DRV8313 internal OCP | HW break from driver nFAULT, SW OCP from INA240, TVS, NTC |
