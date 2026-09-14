# 01 — Parts analysis & sufficiency for 3 drivers

Source material analysed:

| File | What it is |
|---|---|
| `invoice_3680169.pdf` | Robu.in tax invoice INV2627/228307 (05-Sep-2026): the active/passive parts order |
| `order-ST030926127752-export.xlsx` | Connector / NTC / copper-clad order (JST-XH, JST-VH, MF52E103, headers) |
| `SimpleFOCMini-1.0.zip` | **The power stage.** DRV8313 module, 8–24 V, 2.5 A peak, 26×20 mm, 2×5 + 1×3 female headers + screw terminal. Plugs into this board. |
| `LCSampleGerber.zip` | Lion Circuits (Bengaluru) 2-layer sample Gerber — target fab's naming and units |
| user-listed, bought | AO3400 N-FET (unused in spin 1), ERJ8CWFR030V 30 mΩ shunt, STM32G431CBT6 |
| also on hand | SS14 Schottky (40 V 1 A, SMA), through-hole resistor kit |

Spin-1 decisions are in [06-spin1-decisions.md](06-spin1-decisions.md). All
numbers below come from `hardware/calc/design_calcs.py`; the sufficiency
table from `tools/check_bom.py --boards 3`.

---

## 1. What the parts tell us about the intended design

* **SimpleFOC Mini** → the three-phase bridge, gate drive, dead time,
  overcurrent/UVLO/thermal protection and nFAULT are all inside the DRV8313.
  This board is a **carrier**: MCU, CAN, current sense, encoder ports, buck.
* **INA240A1 ×8 + 30 mΩ shunts** → inline phase-current sensing between the
  Mini's OUT1/OUT2 and the motor connector — the Mini has none of its own.
  One 30 mΩ per phase gives ±2.5 A, which is exactly the DRV8313's peak.
  8 INA240 = 2 per board (+2 spare) → 2-shunt FOC, Ic = −Ia−Ib.
* **SN65HVD230 ×4 + 120 Ω ×100** → 3.3 V classic CAN, 3 nodes + spare.
* **AMS1117-3.3 straight off the 12 V bus.** No switcher at all: the LDO
  drops 8.7 V at the measured ~76 mA load = 0.66 W, which a SOT-223 sheds into
  a copper pour. MP1584 module, CD43 and SS14 all unused. The Mini's 3.3 V pin
  is the DRV8313's own LDO, 30 mA max — nowhere near enough — so it stays
  **unconnected**.
* **8 MHz crystal + 30 pF** → HSE for CAN timing.
* **470 µF 50 V ×6** → two at the DC input per board (the Mini adds 100 µF).
* **10 µF 25 V ×14** → 3.3 V rail only (101 % of rating at 25.2 V).
* **AO3481 ×2, AO3400** → unused (keyed connector; Mini is the bridge).
* **MF52E103 NTC ×5** → motor winding temperature, on the encoder cable.
* **JST-VH 2-pin** → DC in and VM feed to the Mini. **JST-XH 3-pin** → motor
  phases, CAN in, CAN out. **JST-XH 5-pin** → AS5600 + NTC.
* **Single-sided copper clad ×4** → not usable for this board (§5).

Invoice resistor lines, re-checked: **4.7 k ×16, 10 k ×30, 0 Ω ×44, 120 Ω
×100, 2.2 k ×100 — all 1206.** Nothing else; the THT kit supplies the 100 k.

## 2. Capability of the board as specified

### 2.1 Power stage — SimpleFOC Mini (DRV8313)

| | |
|---|---|
| VM | 8–24 V per the Mini README (DRV8313 60 V; the Mini's 100 µF is 35 V). The arm runs at **12 V from one shared 5 A PSU** over the harness; 24 V stays a PSU-only option |
| Peak phase current | 2.5 A (DRV8313 rating) |
| Continuous | ≈ 1.5 A rms — conduction 3 × I² × 0.2 Ω ≈ 1.35 W on the Mini's 26×20 mm board, ~55 °C rise; 1.75 A rms is "hot" |
| Control | 3-PWM (IN1-3) + EN; dead time internal; nSLEEP, nRESET, nFAULT |
| Protection | OCP, UVLO, thermal shutdown → nFAULT (open-drain, 10 k pull-up on the Mini) |
| Header (H1, 2×5) | 1 GND · 2 3.3V-out (**NC on carrier**) · 3 IN1 · 4 GND · 5 IN2 · 6 nRESET · 7 IN3 · 8 nSLEEP · 9 EN · 10 nFAULT |
| Phase header (P1, 1×3) | 1 OUT3 · 2 OUT2 · 3 OUT1 |
| Power | screw terminal VM/GND → short wire pair from the carrier's J6 |

### 2.2 Current sense — INA240A1 (20 V/V) + ERJ8CWFR030V (30 mΩ, 1 W)

| Shunt | Sensitivity | Range | ADC LSB | Shunt power at range |
|---|---|---|---|---|
| **single 30 mΩ (spin 1)** | 0.60 V/A | **±2.5 A pk (1.77 A rms)** | 1.3 mA | 0.19 W of 1 W |
| 2 × 30 mΩ ‖ (spin 2, discrete bridge) | 0.30 V/A | ±5.0 A pk | 2.7 mA | 0.38 W of 2 W |

The single shunt's ±2.5 A is an exact match to the DRV8313 peak; the amplifier
saturates just where the driver's own OCP takes over. **6 shunts for 3 boards.**

### 2.3 Spin-1 design point

| Parameter | Value | Set by |
|---|---|---|
| DC bus | **12 V only** (8–15 V) | the AMS1117 fed directly: 18 V abs max and 0.66 W already at 12 V |
| Peak phase current | **±2.5 A** | DRV8313 = INA240 range |
| Continuous phase current | **~1.5 A rms** | DRV8313 thermal on the Mini |
| Peak / continuous electrical | ≈ 30 W / ≈ 20 W per joint at 12 V | a high-R gimbal motor is voltage-limited before the driver: see docs/08 |
| Carrier dissipation | ≈ 0.5 W (the Mini dissipates its own ~1.4 W) | 2-layer 1 oz fine |
| PWM | 20 kHz centre-aligned, 12.1-bit, 3-PWM | TIM1 @ 170 MHz |
| Upgrade | spin 2: discrete bridge with the AO3400s in the drawer → ±5 A (docs/06) | |

### 2.4 Communication — SN65HVD230 (1 Mbps classic CAN)

3 joints at 1 kHz: 4-byte command + 8-byte feedback = 68 % bus load. Footprint
is pin-compatible with TCAN332 (3.3 V, 5 Mbps CAN-FD) for later.

### 2.5 Logic supply — AMS1117-3.3 direct, no switcher

One part instead of three. The itemised 3V3 load is **76 mA** (MCU 30, CAN 15,
2 × INA240 5, AS5600 6.5, joint encoder 15, LEDs and pull-ups 4), so the LDO
drops 8.7 V at 76 mA = **0.66 W**:

| Bus | P in the LDO | ΔT (55 °C/W pour) | ΔT (80 °C/W) | Tj at 40 °C ambient | |
|---|---|---|---|---|---|
| **12 V, real load** | 0.66 W | 36 °C | 53 °C | **93 °C** | OK |
| 12 V, 100 mA budget | 0.87 W | 48 °C | 70 °C | 110 °C | hot, wants a good pour |
| 15 V | 1.17 W | 64 °C | 94 °C | 134 °C | over Tj(max) |
| 24 V | 2.07 W | — | — | — | over Tj *and* over the 18 V abs-max input |

**This fixes the board at 12 V.** The AMS1117's 18 V absolute maximum and its
dissipation are now the bus ceiling, not the DRV8313 — firmware trips at 15 V.
A higher bus means putting a switching pre-regulator back in front of the LDO.

Pour copper on U8's tab (it is pin 2 / VO) and keep it away from the shunts
and the INA240s. Dropout is ~1.1 V at this load, so the LDO is comfortable long
before the DRV8313's 8 V UVLO. PSRR runs ~60 dB at low frequency falling to
~40 dB by 20 kHz; the 2 × 470 µF bulk plus C5/C21 at the input keep PWM ripple
off the rail, and VDDA still sits behind R23 + C11/C12/C13. Everything analog
is ratiometric to 3V3.

### 2.6 Connectors

* J1 JST-VH 2P — 12 V in. J13 JST-VH 2P — 12 V out to the next joint (pass-through). J6 JST-VH 2P — VM out, wired to the Mini's terminal.
* J2 JST-XH 3P — phases (~3 A/pin; fine at 2.5 A peak).
* J3 JST-XH 5P — 3V3, GND, SCL, SDA, NTC → AS5600 + thermistor.
* J4 / J5 1×6 (from the female strip) — SPI_A (motor-side upgrade), SPI_B
  (output-side absolute encoder).
* J7 2×5 + J8 1×3 — Mini socket (male pins; the Mini's headers are female).
* CAN in / out — two JST-XH 3P (CANH, CANL, GND).

## 3. Sufficiency for 3 boards

`python3 tools/check_bom.py --boards 3`:

| Part | per board | ×3 | on hand | Status |
|---|---|---|---|---|
| SimpleFOC Mini | 1 | 3 | bought | confirm ≥ 3 |
| STM32G431CBT6 | 1 | 3 | bought | confirm ≥ 3 |
| ERJ8CWFR030V | 2 | 6 | bought | confirm ≥ 6 |
| SS14 | 1 | 3 | have | confirm ≥ 3 |
| 100 k (THT kit) | 1 | 3 | have | OK |
| SN65HVD230DR | 1 | 3 | 4 | OK |
| INA240A1DR | 2 | 6 | 8 | OK |
| CD43 3.3 µH | 1 | 3 | 4 | OK |
| 8 MHz crystal / 30 pF | 1 / 2 | 3 / 6 | 6 / 12 | OK |
| 470 µF 50 V | 2 | 6 | 6 | OK, zero spare |
| AMS1117-3.3 | 1 | 3 | 5 | OK |
| 10 µF 25 V | 3 | 9 | 14 | OK |
| 100 nF 250 V | 11 | 33 | 50 | OK |
| MP1584 module, SS14, CD43 3.3 µH | 0 | — | — | no longer used |
| 1 µF 50 V | 4 | 12 | 22 | OK |
| 10 k / 4.7 k / 2.2 k / 120 Ω / 0 Ω | 6 / 4 / 6 / 1 / 5 | 18 / 12 / 18 / 3 / 15 | 30 / 16 / 100 / 100 / 44 | OK |
| Red LED | 2 | 6 | 9 | OK |
| NTC | 1 | 3 | 5 | OK |
| JST-VH 2P | 3 | 9 | 10 | OK, one spare |
| JST-XH 3P | 3 | 9 | 10 | OK, one spare |
| JST-XH 5P | 1 | 3 | 5 | OK |
| 1×40 female header | 19 pos | 57 | 160 | OK |
| AO3481, AO3400, HC49/U, CD43, SS14, copper clad | 0 | — | — | not used |

## 4. What to buy

| # | Part | Qty | Why |
|---|---|---|---|
| 1 | Male pin header strip (for 2×5 + 1×3 per board) | 1 strip | Mini socket — skip if your Mini came with male pins (then use the female strip you have) |
| 2 | SMBJ15A | 4 | VBUS hot-plug clamp — optional |
| 3 | 2-layer PCB, Lion Circuits | 5 | |

That is the whole list — two lines of it optional. Counts to confirm on hand:
SimpleFOC Mini ≥ 3, STM32G431CBT6 ≥ 3, ERJ8CWFR030V ≥ 6. Optional later: MT6701
breakout + 6 × 2.5 mm diametric magnet ×3 for the joint encoder on J5.

## 5. The copper-clad boards are not usable for this design

LQFP-48 escape routing, Kelvin-connected shunts and a CAN pair need two copper
layers with a ground pour. 2-layer from Lion Circuits is fine — at ~0.5 W on
the carrier, 1 oz is enough.

## 6. Reference-design comparison

| | SimpleFOCMini alone | This carrier + Mini |
|---|---|---|
| MCU | external Arduino, 4 wires | on-board STM32G431 |
| Current sense | none | 2 × INA240 inline, ±2.5 A |
| Interface | PWM pins | CAN 1 Mbps, node-ID straps |
| Encoder | external | AS5600 (I2C) + two SPI ports |
| Supply | 3.3 V @ 30 mA from DRV8313 | own AMS1117 off the 12 V bus |
| Protection | DRV8313 internal | + TIM1 hardware break on nFAULT, SW OCP, TVS, NTC |
