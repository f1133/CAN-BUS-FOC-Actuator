# 06 — Spin-1 decisions, bottleneck upgrades, first-PCB checklist

Decisions taken for the first PCB order, and what each one changed.

## Decisions

| Decision | Consequence in the design |
|---|---|
| **The SimpleFOC Mini is the power stage**, plugged into the board. | The board is a carrier: STM32G431, CAN, 2 × INA240 inline sense, buck, encoder ports, Mini socket. No gate driver, gate rail, gate resistors or discrete FETs. 3-PWM control (IN1-3 + EN), nSLEEP/nRESET on GPIOs, nFAULT to the TIM1 break input. The Mini's 3.3 V pin stays unconnected (30 mA LDO; must not be paralleled with the carrier rail). |
| **One board drives one motor.** | Three carriers, three Minis, three motors. |
| **Max spec from the parts.** | The DRV8313's 2.5 A peak is matched exactly by one 30 mΩ + INA240A1 (±2.5 A, 1.3 mA/LSB): 6 shunts total. ~1.5 A rms continuous from the Mini's thermal budget. |
| **One 12 V / 5 A PSU for the whole arm, over the harness.** | Bus 12 V; each board passes power through J1 → J13 (≥ 2 mm trace, the first board carries all 5 A). At 12 V a gimbal winding, not the driver, sets stall current ((12 V/√3)/R); 24 V would double it with no board change — docs/08. |
| **Logic supply: module → 5 V → AMS1117-3.3.** | The **MP1584 module on hand** (proven circuit; a discrete MP1584EN's BST/COMP values are unverified here) is trimmed to 5 V; the AMS1117-3.3 from the invoice makes 3V3 fixed and LDO-clean, so a bumped trimmer cannot put 3.6 V+ on the MCU. 0.17 W. CD43 and SS14 unused. |
| **AS5600 motors** (as shipped). | I2C1 on J3 = 3V3, GND, SCL, SDA, NTC — one cable to the motor. |
| **Cycloidal actuator.** | Motor-side encoder cannot give joint-absolute position → **SPI encoder on the output shaft (J5)**. Second AS5600 impossible (fixed address), hence SPI. |
| **SPI for future encoder upgrade.** | J4 (PA4 CS, motor side) and J5 (PA15 CS, output side) on SPI1; PA7 = MOSI. |
| **2-layer PCB from Lion Circuits.** | ~60 × 60 mm; the carrier dissipates ~0.5 W, 1 oz is fine. |
| 25 V 10 µF ceramics kept off VBUS. | 101 % of rating at 25.2 V. 100 nF 250 V / 1 µF 50 V on the bus. |
| Reverse-polarity FET dropped. | JST-VH is keyed. |
| **Bought parts kept for spin 2.** | AO3400 ×(≥18), FD6288T-style discrete bridge → ±5 A with the parallel shunts and PB13/14/15 as CH1N-3N. Firmware `-DBRIDGE_DISCRETE`. Documented, not built. |

## Bottleneck upgrades, ranked

| # | Bottleneck | Limit today | Upgrade | Cost |
|---|---|---|---|---|
| 1 | Phase current | DRV8313 2.5 A pk / ~1.5 A rms | **Spin 2 discrete bridge** with the AO3400s on hand + FD6288T + 10 V rail + 22 Ω → ±5 A. New PCB. | ~₹300 + PCB |
| 2 | Mini thermal | ~1.35 W on 26 × 20 mm | screw the Mini to the carrier's pour with a thermal pad; airflow | ₹0 |
| 3 | Motor-side encoder | AS5600 I2C, 1 kHz, 12-bit | MT6701 / AS5047P on **J4** — no PCB change | ~₹150 |
| 4 | Joint-absolute position | none without J5 (homing at boot) | MT6701 / AS5047P + 6 mm diametric magnet on the output shaft, **J5** — no PCB change | ~₹150 + magnet |
| 5 | CAN bandwidth | 1 Mbps classic, 68 % at 1 kHz × 3 joints | TCAN332 in the same footprint — no PCB change | ~₹80 |
| 7 | Joint torque with high-R gimbal motors | voltage-limited at 12 V | 24 V PSU: 2× stall current on a 6–10 Ω winding, board and Mini unchanged | one PSU |
| 6 | Phase connector | JST-XH 3-pin ~3 A/pin | only matters for spin 2 | — |

## Encoder mounting (3D-printed)

With a printer the joint encoder can go exactly where it should — on the
rotation axis of the cycloidal output — so plan the parts around that:

* **Magnet on the axis.** 6 × 2.5 mm diametrically magnetised disc pressed
  into a printed cup on the output shaft centre (or the cycloidal's output
  disc). Runout ≤ 0.2 mm, air gap 0.5–2 mm to the sensor face. No screw heads
  or steel within ~5 mm of the magnet; nylon/brass screw or press fit.
* **Sensor on a printed bracket** bolted to the fixed housing, with two
  adjustment slots so the magnet-to-chip centring can be dialled in. The
  common MT6701 / AS5047P breakouts are ~15 × 15 mm with 2 holes.
* **Hollow output?** Magnet on a printed spoke across the bore end, or an
  off-axis magnetic ring (MT6835 / AS5x47 ring mode) — same SPI port.
* **Motor side** stays as shipped (AS5600 on the motor's back).
* **Carrier + Mini**: printed spacer on the motor back plate using the 40 mm
  hole square; the Mini sits on the carrier's pour with a thermal pad; keep-out
  over the motor's AS5600 board; J5 cable stays inside the housing.

## First-PCB checklist (things that save a respin)

* **Every IC gets a 100 nF within 2 mm.** INA240 VS ×2, SN65HVD230, MCU ×3 + VDDA.
* **DRV_EN pull-down and BOOT0 pull-down** on the carrier (nFAULT/nSLEEP/nRESET pull-ups are on the Mini).
* **Mini 3.3V pin (H1.2): no copper.** Label it NC on the silkscreen.
* **Bridge-disable jumper**: 0 Ω site in series with DRV_EN so the logic can be brought up with the Mini unable to switch.
* **Test points**: 3V3, VBUS/10, ISENSE_A/B (expect 1.65 V idle), nFAULT, each phase.
* **Kelvin the shunts**: INA240 IN+/IN− traces from the inner edge of the shunt pads.
* **ADC input RC (10 Ω + 1 nF) sites** on ISENSE_A/B even if populated with 0 Ω.
* **Mini socket orientation**: silkscreen the H1 pin-1 corner and the P1 OUT3/OUT2/OUT1 order; a reversed Mini puts 24 V onto logic pins.
* **SWD header** (3V3, SWDIO, SWCLK, GND) and **UART header** (TX, RX, GND) from the strip; label them.
* **Silkscreen the node-ID straps and CAN-termination jumper.**
* **Mounting holes on a 40 mm square**, plus one under the Mini's hole; keep-out under the motor's AS5600 board.
* **First power-up**: bench supply current-limited to 200 mA, bridge-disable jumper open, Mini unplugged; check 3V3, then plug the Mini in.

## Firmware build flags

| Flag | Effect |
|---|---|
| (default) | SimpleFOC Mini: 3-PWM, 30 mΩ, ±2.5 A, VBUS 8–16 V (12 V PSU) |
| `-DBRIDGE_DISCRETE` | spin-2 6-PWM bridge: 15 mΩ, ±5 A, dead time 400 ns, AO3400 limits (16 V) |
| `-DBRIDGE_DISCRETE -DBRIDGE_FET_AOD4184` | spin-2 with AOD4184: 24 V |
| `GEAR_RATIO` | set to the real cycloidal ratio in `foc_config.h` |
