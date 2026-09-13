# 01 — Parts analysis & sufficiency for 3 drivers

Source material analysed:

| File | What it is |
|---|---|
| `invoice_3680169.pdf` | Robu.in tax invoice INV2627/228307 (05-Sep-2026): the active/passive parts order |
| `order-ST030926127752-export.xlsx` | Connector / NTC / copper-clad order (JST-XH, JST-VH, MF52E103, headers) |
| `SimpleFOCMini-1.0.zip` | Reference design: DRV8313 (integrated 2.5 A FETs), 8–24 V, 26×20 mm, EasyEDA + Altium + Gerbers |
| `LCSampleGerber.zip` | Lion Circuits (Bengaluru) 2-layer sample Gerber — tells us the target fab's file naming and units (imperial, `TOP.GTL/BOTTOM.GBL/OUTLINE.GKO/DRILL.drl`) |
| user-listed | AO3400 N-FET, ERJ8CWFR030V 30 mΩ shunt, STM32G431CBT6 |

All numbers below are produced by `hardware/calc/design_calcs.py`; the
sufficiency table by `tools/check_bom.py --boards 3`.

---

## 1. What the parts tell us about the intended design

Reading the invoice as a design, not a list:

* **INA240A1 ×8 + 30 mΩ 1206 shunts** → **inline (phase) current sensing**, not
  low-side. INA240 exists specifically for this: −4…+80 V common-mode with
  PWM-edge rejection, so the shunt sits *in the motor phase* and can be sampled
  at any point in the PWM cycle. That is the single biggest quality upgrade over
  the SimpleFOCMini reference (which has no current sense at all).
* **8 INA240 for 3 boards = 2 per board (+2 spare)**. A 3-shunt design would need
  9. So the design is **2-shunt FOC** (Ia, Ib measured; Ic = −Ia−Ib). That is
  the standard, fully adequate topology; the third shunt is a reserved option
  (pin PA7 / ADC2_IN4 is kept free for it).
* **SN65HVD230 ×4 + 120 Ω ×100** → 3.3 V CAN bus, 3 nodes + spare, termination
  on the end nodes.
* **CD43 3.3 µH ×4 + AMS1117-3.3 ×5** → a two-stage logic supply:
  `24 V → buck → 5 V → LDO → 3.3 V`. 3.3 µH is the right inductor for a
  ~1.4 MHz 24→5 V buck at a few hundred mA (ΔI ≈ 0.86 A, peak 0.58 A, inside the
  1 A saturation rating). **It is not** sized for a 24→12 V gate-drive buck.
* **8 MHz crystal ×6 + 30 pF ×12** → HSE for the MCU. 30 pF load caps are
  correct for the crystal's 20 pF CL (2 × (20 − ~5 pF stray) = 30 pF). HSE is
  needed because HSI16 (±1 %) is marginal for 1 Mbps CAN bit timing.
* **470 µF 50 V ×6** → two bulk DC-link caps per board. 50 V rating on a 24 V
  bus is a healthy margin.
* **AO3481 P-FET ×2** → reverse-polarity protection on VBUS. Only two, for three
  boards.
* **MF52E103 NTC ×5** → motor winding temperature, one per board.
* **JST-VH 2-pin (10 A)** → DC input. **JST-XH 3-pin** → motor phases.
  **JST-XH 5-pin** → encoder.
* **Single-sided copper clad ×4** → home etching intent. See §5: not viable for
  this board.

## 2. Capability of the board as specified

### 2.1 Power stage — AO3400A (30 V, 28 mΩ @ 10 V, SOT-23)

| Item | Value | Comment |
|---|---|---|
| Vds max | 30 V | **Margin at 25.2 V (6S full) is 4.8 V.** Switching ringing on a motor half-bridge routinely exceeds that → avalanche. |
| Thermal continuous phase current | ≈ 4.9 A rms at Vgs = 10 V, ≈ 4.2 A rms at 4.5 V | θJA ≈ 140 °C/W (SOT-23, ~1 in² 2 oz copper), Tj ≤ 125 °C at 40 °C ambient. The datasheet 5.8 A is a Tc = 25 °C number and is not reachable on FR4. |
| Vgs abs max | **±12 V** | Gate rail must be ≤ 10–11 V. This rules out drivers with a fixed ~12 V+ gate supply. |
| Qg | ~9 nC @ 10 V | Trivial gate-drive current: 6 × 9 nC × 20 kHz ≈ 1 mA. The gate-drive rail can be a **10 V zener / 78L10**, no buck needed. |

**Recommendation:** run the bus at **12–18 V (4S)** with these FETs. If you want
24 V, swap to a ≥ 40 V FET in the same footprint (e.g. AO3420-class is still
20 V — use a 40/60 V SOT-23 or move to SOT-23-6 / DFN). Everything else in the
design is 24 V-capable, so the swap is one footprint-compatible part.

### 2.2 Current sense — INA240A1 (20 V/V) + ERJ8CWFR030V (30 mΩ, 1 W)

INA240 at 3.3 V with REF = VS/2 (REF1 = VS, REF2 = GND) gives ±1.5 V of usable
output swing:

| Shunt | Sensitivity | Measurable range | ADC LSB | Shunt power at range |
|---|---|---|---|---|
| single 30 mΩ | 0.60 V/A | **±2.5 A pk (1.77 A rms)** | 1.3 mA | 0.19 W of 1 W |
| **2 × 30 mΩ in parallel = 15 mΩ** | 0.30 V/A | **±5.0 A pk (3.54 A rms)** | 2.7 mA | 0.38 W of 2 W |

A single 30 mΩ shunt saturates the amplifier at only 2.5 A — below the FETs'
thermal limit. **Two shunts in parallel per phase (15 mΩ)** gives ±5 A peak,
which matches the FET thermal limit almost exactly and keeps 2.7 mA resolution.
The design therefore uses **4 shunts per board, 12 total.**

### 2.3 Resulting design point

| Parameter | Value | Set by |
|---|---|---|
| DC bus | **12–18 V** (24 V only with ≥ 40 V FETs) | AO3400 Vds |
| Peak phase current | **±5 A** | INA240 + 15 mΩ |
| Continuous phase current | **3.5 A rms** | current-sense range (FET thermal allows ~4.9 A) |
| Board dissipation at 3.5 A rms | ≈ 3.1 W | needs 2 oz copper + thermal vias |
| PWM | 20 kHz centre-aligned, 12.1-bit duty; 40 kHz possible at 11.1-bit | TIM1 @ 170 MHz |
| Dead time | 400 ns (68 × tDTS) | AO3400 + 120/22 Ω gate R |
| Motor size this suits | gimbal / small NEMA17-class BLDC, ~30–80 W joint | |

That is a coherent, useful robot-arm-joint driver. It is not a 24 V / 10 A
driver, and the parts on hand should not be pushed to pretend it is.

### 2.4 Communication — SN65HVD230 (1 Mbps classic CAN)

* Transceiver maxes at 1 Mbps → FDCAN peripheral runs in **classic CAN mode**
  (or FD with data-phase ≤ 1 Mbps, which gains nothing).
* Bus load with 3 joints, 1 command + 1 feedback frame each, at 1 kHz:
  * 8-byte frames: **80 %** → too high.
  * 4-byte frames: **57 %** → workable.
* So the protocol (doc 05) uses compact 4–6-byte frames at 1 kHz, or 8-byte at
  500 Hz feedback. If you later want 5 Mbps CAN-FD, drop in a TCAN1042 /
  MCP2562FD (same SOIC-8 pinout family) and nothing else changes.

### 2.5 Logic supply — AMS1117-3.3

| Input | Dissipation @ 150 mA | ΔT (SOT-223, ~60 °C/W) | Verdict |
|---|---|---|---|
| 5 V (from buck) | 0.26 W | 15 °C | **OK** |
| 12 V | 1.30 W | 78 °C | fail |
| 24 V direct | 3.10 W | 186 °C | fail — and exceeds the 15 V abs-max input |

The AMS1117 **must** hang off the 5 V buck. The buck IC itself is not in the
order (see §4).

### 2.6 Connectors

* JST-VH 2-pin, 3.96 mm, 10 A — correct for DC input.
* **JST-XH 3-pin for motor phases is rated ~3 A per contact.** That is at the
  design's 3.5 A rms continuous. Acceptable for a first prototype at ≤ 3 A;
  for the full 5 A peak / 3.5 A rms use JST-VH 3-pin or screw terminals on the
  next spin. Flagged, not blocking.
* **JST-XH 5-pin for the encoder = VCC, GND + 3 signals.** This is enough for:
  * MT6701 / AS5047 in **SSI/3-wire read-only** mode (CSN, CLK, DO) ✔
  * AS5600 **I2C** (SCL, SDA + spare) ✔
  * incremental **ABI/ABZ** ✔ · **hall** sensors ✔
  * …but **not** full 4-wire SPI (needs MOSI too). The board routes the 3
    signal pins so that firmware + 0 Ω option jumpers select the mode
    (doc 03). Recommended encoder: **MT6701 over SSI** (14-bit, 1 MHz clock,
    no MOSI needed).

## 3. Sufficiency for 3 boards

`python3 tools/check_bom.py --boards 3`:

| Part | per board | ×3 | on hand | Status |
|---|---|---|---|---|
| STM32G431CBT6 | 1 | 3 | ? | user to confirm — buy 4 |
| SN65HVD230DR | 1 | 3 | 4 | OK (+1) |
| INA240A1DR | 2 | 6 | 8 | OK (+2) |
| AMS1117-3.3 | 1 | 3 | 5 | OK (+2) |
| CD43 3.3 µH | 1 | 3 | 4 | OK (+1) |
| 8 MHz SMD crystal | 1 | 3 | 6 | OK |
| 30 pF | 2 | 6 | 12 | OK |
| 470 µF 50 V | 2 | 6 | 6 | **OK, zero spare** |
| 10 µF 25 V 1206 | 4 | 12 | 14 | OK (tight) |
| 100 nF 1206 | 13 | 39 | 50 | OK |
| 1 µF 50 V 1206 | 8 | 24 | 22 | **short by 2** (substitute 100 nF for the 5 V-rail ones) |
| 10 k | 9 | 27 | 30 | OK (tight) |
| 4.7 k | 2 | 6 | 16 | OK |
| 2.2 k | 2 | 6 | 100 | OK |
| 120 Ω | 1 | 3 | 100 | OK |
| 0 Ω | 8 | 24 | 44 | OK |
| Red LED | 2 | 6 | 9 | OK |
| **AO3481 P-FET** | 1 | 3 | 2 | **short by 1** |
| AO3400A | 6 | 18 | ? | user to confirm — buy 24 |
| ERJ8CWFR030V | 4 | 12 | ? | user to confirm — buy 15 |
| NTC MF52E103 | 1 | 3 | 5 | OK |
| JST-VH 2P RA | 1 | 3 | 10 | OK |
| JST-XH 3P RA | 1 | 3 | 10 | OK |
| JST-XH 5P RA | 1 | 3 | 5 | OK |
| 1×40 header | 7 pos | 21 | 160 | OK |

## 4. What is missing (blockers)

These are **not in any of the files** and the board cannot work without them:

| # | Part | Why | Suggested part (Indian availability) | Qty for 3 |
|---|---|---|---|---|
| 1 | **3-phase gate driver** | Six N-FETs need bootstrap high-side drive. Nothing in the order drives a gate. | **FD6288T** (TSSOP-16, integrated bootstrap diodes + shoot-through lockout, 600 V) or **EG2133**. Both take 3.3 V logic. | 3 (+2) |
| 2 | **5 V buck IC** | The 3.3 µH inductor is there; the switcher isn't. | **MP2451 / MP1584EN** (SOT23-6/SOIC-8, ~1.4 MHz, 24 V in) or TPS54202. | 3 (+2) |
| 3 | **10 V gate-drive rail** | Gate driver VCC; AO3400 Vgs max is ±12 V so 12 V is too close. Only ~2 mA needed. | **78L10** (SOT-89/TO-92) or 10 V 1 W zener + 1 kΩ from VBUS | 3 |
| 4 | **Gate resistors 22 Ω** | 120 Ω in stock gives ~290 ns edges and ~0.3–0.4 W switching loss per FET at 20 kHz — usable as a fallback only at ≤ 20 kHz. | 22 Ω 1206 | 18 (+6) |
| 5 | **Buck catch diode** | Only if an asynchronous buck (MP1584) is chosen. | SS34 (SMA) | 3 |
| 6 | **VBUS TVS** | 30 V FETs on a motor bus need a clamp. | SMBJ18A (16 V bus) / SMBJ26A (24 V) | 3 |
| 7 | **Absolute encoder + magnet** | FOC needs rotor angle; a robot arm needs it *absolute at power-on*. Not in any file. | **MT6701** (SSI over the 5-pin JST) + 6 mm diametric magnet | 3 |
| 8 | **AO3481 ×1 more** | 3rd reverse-polarity FET. (Or drop the P-FET; JST-VH is keyed.) | AO3481 | 1 |
| 9 | **4-layer PCB** | See §5 | JLCPCB / Lion Circuits 4-layer, 2 oz outer | 5 |

Nice-to-have: 1 µF ×2 more, CAN common-mode choke, polyfuse on VBUS.

## 5. The copper-clad boards are not usable for this design

The order includes 4 × single-sided 7.6 × 10 cm copper clad — a home-etch
intent. This board has an LQFP-48 (0.5 mm pitch), three half-bridges that need
a solid ground return, two INA240s measuring 15 mΩ (kelvin connections), and a
1 Mbps CAN pair. That needs:

* ≥ 2 layers for escape routing of the LQFP-48 (realistically 4 for a clean
  ground plane under the analog front-end),
* 2 oz copper for the phase pours,
* thermal vias under the SOT-23s.

Single-sided etching cannot deliver any of that. Use the copper clad for a
motor-side encoder/NTC breakout or a test jig; order the driver as a 4-layer
board. The Lion Circuits sample confirms they accept the standard Protel
extensions, so the KiCad/EasyEDA export will drop straight in.

## 6. Reference-design comparison (SimpleFOCMini)

| | SimpleFOCMini v1.0 | This design |
|---|---|---|
| Driver | DRV8313, integrated FETs | 6 × AO3400 + FD6288T |
| Current | 2.5 A/phase, no sensing | 5 A pk / 3.5 A rms, 2-shunt inline INA240 |
| MCU | none (external Arduino) | on-board STM32G431 |
| Interface | 3× PWM + EN pins | CAN bus, 1 Mbps, node-ID straps |
| Encoder | external | on-board SSI/I2C master, 5-pin JST |
| Size | 26 × 20 mm, 2-layer | ~50 × 50 mm, 4-layer |
| Protection | DRV8313 internal OCP | HW break from driver nFAULT, SW OCP from INA240, TVS, NTC |

The SimpleFOCMini schematic is a useful sanity reference for the DRV8313-era
signal names used by the SimpleFOC library (EN, IN1-3, nFAULT, nSLEEP, nRESET)
that the firmware layer keeps compatible with.
