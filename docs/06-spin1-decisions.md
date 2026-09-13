# 06 — Spin-1 decisions, bottleneck upgrades, first-PCB checklist

Decisions taken for the first PCB order, and what each one changed.

## Decisions

| Decision | Consequence in the design |
|---|---|
| **No 5 V rail.** Nothing needs it (STM32, SN65HVD230, INA240, AS5600 all 3.3 V). | MP1584EN runs straight to 3.3 V (t_on 137 ns at 24 V, ripple 0.86 A, DCM). AMS1117 unused. Frees 2 × 1 µF + 2 × 10 µF per board. |
| **AS5600 motors** (as shipped). | I2C1 PB6/PB7 is the default encoder; J3 = 3V3, GND, SCL, SDA, NTC — one cable to the motor. The SPI-mode 0 Ω jumpers and MT6701 purchase are gone. |
| **2-layer PCB from Lion Circuits.** | OK at 3.5 A rms / 24 V with a bottom-layer ground pour and 2 oz copper. ~60 × 60 mm. The single-sided copper clad stays unused. |
| **Cycloidal actuator.** | Motor-side encoder cannot give joint-absolute position → dual encoder: AS5600 for commutation, **SPI encoder on the output shaft (J5)** for joint position. Fixed AS5600 address rules out a second I2C device, so the second port is SPI. |
| **SPI for future encoder upgrade.** | Two 1×6 SPI headers cut from the female strip, shared SCK/MISO/MOSI, separate CS: J4 (PA4, motor side) and J5 (PA15, output side). PA7 became SPI1_MOSI; the 3rd-shunt option was dropped (8 INA240 ÷ 3 boards anyway). |
| **Max spec from the parts.** | 2 × 30 mΩ in parallel per phase → ±5 A pk / 3.5 A rms, 12 shunts. |
| **Bottleneck update: bridge FET.** | AO3400 (30 V) capped the bus at 16 V and was the thermal limit. **AOD4184** (TO-252, 40 V, 8 mΩ) → 24 V bus, FET thermal limit ≈ 15 A rms, easier to solder. AO3400 kept as a 16 V build option (`-DBRIDGE_FET_AO3400`). |
| Reverse-polarity FET dropped. | JST-VH is keyed; the 3rd AO3481 no longer needs buying. |
| 25 V 10 µF ceramics moved off VBUS. | 101 % of rating at 25.2 V. 100 nF 250 V and 1 µF 50 V take their place on the bus. |

## Bottleneck upgrades, ranked

Things that limit the board at the spin-1 design point, cheapest first. None
require a PCB change except where noted.

| # | Bottleneck | Limit today | Upgrade | Cost |
|---|---|---|---|---|
| 1 | Bridge FET voltage/thermal | AO3400: 16 V, ~5 A rms | **AOD4184 — taken for spin 1** | ~₹10/pc |
| 2 | Phase connector | JST-XH 3-pin, ~3 A/pin | JST-VH 3-pin or 5.08 mm screw terminal (footprint decision at layout) | ~₹5 |
| 3 | Copper | 1 oz at 3.5 A rms is warm | order 2 oz | fab option |
| 4 | Motor-side encoder rate/latency | AS5600 I2C, 1 kHz reads, 12-bit, 0.29 ms filter | MT6701 (SSI, 14-bit) or AS5047P on **J4** — no PCB change | ~₹150 |
| 5 | Joint-absolute position | none without J5 (homing at boot) | MT6701 / AS5047P + 6 mm diametric magnet on the output shaft, **J5** — no PCB change | ~₹150 + magnet |
| 6 | CAN bandwidth | 1 Mbps classic, 68 % load with 3 joints at 1 kHz | TCAN332 (3.3 V, 5 Mbps FD) in the same footprint — no PCB change | ~₹80 |
| 7 | Current-sense range | ±5 A (sense-limited, FETs have 3× margin) | 3 × 30 mΩ ‖ (10 mΩ) → ±7.5 A; needs the VH phase connector and 2 oz first | 6 more shunts/board |
| 8 | Gate resistors | 22 Ω → 1.3 W switching loss at 3.5 A/20 kHz on AOD4184 | 10 Ω if EMI/ringing allows, or drop PWM to 16 kHz | ₹1 |

## Encoder mounting (3D-printed)

With a printer the joint encoder can go exactly where it should — on the
rotation axis of the cycloidal output — so plan the parts around that:

* **Magnet on the axis.** 6 × 2.5 mm diametrically magnetised disc pressed
  into a printed cup on the output shaft centre (or the cycloidal's output
  disc). Runout ≤ 0.2 mm, air gap 0.5–2 mm to the sensor face. No screw heads
  or steel within ~5 mm of the magnet; use a nylon/brass screw or a press fit
  for the cup.
* **Sensor on a printed bracket** bolted to the fixed housing, with two
  adjustment slots so the magnet-to-chip centring can be dialled in (an
  off-centre magnet shows up as a once-per-turn angle error). The common
  MT6701 / AS5047P breakout boards are ~15 × 15 mm with 2 mounting holes.
* **Hollow output?** If the output shaft is bored through (cables to the
  next joint), put the magnet on a printed spoke across the bore end, or use
  an off-axis magnetic ring (MT6835 / AS5x47 in ring mode) — same SPI port.
* **Motor side** stays as shipped (AS5600 on the motor's back). If it is later
  upgraded to SPI on J4, the same printed-cup approach applies to the motor
  shaft end.
* **Driver board**: printed spacer/adapter on the motor back plate using the
  40 mm hole square; keep-out over the motor's AS5600 board; J5 cable to the
  output encoder is short and stays inside the actuator housing.

## First-PCB checklist (things that save a respin)

* **Every IC gets a 100 nF within 2 mm.** INA240 VS, FD6288T VCC, SN65HVD230, MCU ×3 + VDDA.
* **DRV_EN pull-down, nFAULT pull-up, BOOT0 pull-down** — the three resistors that decide whether the board is safe at power-on.
* **Bridge-disable jumper**: a 0 Ω site in series with DRV_EN so the logic can be brought up with the bridge physically unable to switch.
* **Test points**: 3V3, 10 V, VBUS/10, ISENSE_A/B (expect 1.65 V idle), nFAULT, each phase.
* **Kelvin the shunts**: INA240 IN+/IN− traces leave from the inner edge of the shunt pads, not from the current path.
* **ADC input RC (10 Ω + 1 nF) sites** on ISENSE_A/B even if populated with 0 Ω.
* **SWD header** (3V3, SWDIO, SWCLK, GND) and **UART header** (TX, RX, GND) from the strip; label them.
* **Silkscreen the node-ID straps and CAN-termination jumper** so three boards can be set without the schematic.
* **Mounting holes on a 40 mm square**, keep-out under the motor's AS5600 board.
* **First power-up**: bench supply current-limited to 200 mA, bridge-disable jumper open, check 3V3 and 10 V before anything else.

## Firmware build flags

| Flag | Effect |
|---|---|
| (default) | AOD4184, VBUS 10–28 V nominal 24 V |
| `-DBRIDGE_FET_AO3400` | VBUS 10–20 V nominal 16 V |
| `GEAR_RATIO` | set to the real cycloidal ratio in `foc_config.h` |
| `ENC_M_TYPE_AS5600` | motor-side encoder type; SPI types added when J4 is populated |
