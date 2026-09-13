# 02 — Hardware architecture (spin 1: SimpleFOC Mini carrier)

One carrier + one Mini = one joint. Three on one CAN bus.

```
  J1 JST-VH 2P
  VBUS 24 V ──┬── SMBJ26A ──┬── 2×470 µF 50 V ──┬── J6 JST-VH 2P ── wire ──► Mini screw terminal VM/GND
  GND ────────┤             │                    │
              │      ┌──────┴──────┐             │           ┌──────────────────────────────────┐
              │      │ U7 MP1584EN │             │           │ U6 SimpleFOC Mini (DRV8313)      │
              │      │ VBUS→3.3 V  │             │           │ H1 2×5 (J7)        P1 1×3 (J8)   │
              │      │ L1 3.3 µH   │             │           │ 1 GND  2 3.3V(NC)  1 OUT3 ───────┼──► J2.C
              │      │ D1 SS14     │             │           │ 3 IN1  4 GND       2 OUT2 ─ 30mΩ ┼──► J2.B
              │      │ RFREQ 100k  │             │           │ 5 IN2  6 nRESET    3 OUT1 ─ 30mΩ ┼──► J2.A
              │      └──────┬──────┘             │           │ 7 IN3  8 nSLEEP           │  │   │
              │            3V3                   │           │ 9 EN   10 nFAULT          │  │   │
              │             │                    │           └──▲──▲──▲──▲──▲──▲─────────┼──┼───┘
              │  ┌──────────┴───────────┐        │              │  │  │  │  │  │   ┌─────┴──┴─────┐
              │  │ U1 STM32G431CBT6     │        │              │  │  │  │  │  │   │ U3 U4 INA240 │
              │  │ PA8/9/10 TIM1_CH1-3 ─┼────────┼──────────────┘──┘──┘  │  │  │   │ ×20 REF=VS/2 │
              │  │ PB2  DRV_EN ─────────┼────────┼───────────────────────┘  │  │   │              │
              │  │ PB14 nSLEEP  PB15 nRESET ─────┼──────────────────────────┘  │   │              │
              │  │ PB12 TIM1_BKIN ◄─────┼────────┼──────────────────────────────┘   │              │
              │  │ PA0 ADC1_IN1 ◄───────┼────────┼───────────────────────────────────┤ ISENSE_A     │
              │  │ PA1 ADC2_IN2 ◄───────┼────────┼───────────────────────────────────┤ ISENSE_B     │
              │  │ PA2 VBUS 20k:2.2k   PA3 NTC   │                                   └──────────────┘
              │  │ PB6/PB7 I2C1 ────────┼── J3 JST-XH 5P: 3V3 GND SCL SDA NTC  (AS5600 on the motor)
              │  │ PA5/6/7 SPI1, CS PA4/PA15 ──── J4 SPI_A · J5 SPI_B (1×6 each)
              │  │ PA11/12 FDCAN1 ──────┼── U2 SN65HVD230 ── CAN in / CAN out (JST-XH 3P), 120 Ω via 0R
              │  │ PB3/4 USART2 · PA13/14 SWD · PB9 LED · PC13-15 ID · PF0/1 HSE
              │  └──────────────────────┘
```

## 1. Power tree

| Rail | Source | Load | Notes |
|---|---|---|---|
| VBUS 24 V (8–26 V) | J1 (keyed JST-VH) | Mini via J6, buck | SMBJ26A optional. 2 × 470 µF 50 V at J1. **Only 50 V / 250 V ceramics on this rail** — the 10 µF are 25 V. 100 nF 250 V at J6. |
| 3V3 | U7 MP1584EN, L1 CD43 3.3 µH, D1 SS14, RFREQ 100 k (THT), FB 10 k + 4.7 k / 4.7 k, 10 µF + 1 µF out | MCU, INA240 ×2, CAN, AS5600, SPI encoders, LEDs (~100 mA) | No 5 V rail, no LDO. VDDA through a 0 Ω/ferrite site + 1 µF + 100 nF; VREF+ = VDDA. |
| Mini 3.3V-out (H1.2) | DRV8313 V3P3OUT, 30 mA max | — | **Not connected** to the carrier's 3V3: two regulators must not be paralleled, and it can't carry the load anyway. It only feeds the Mini's own pull-ups. |

## 2. Power stage — SimpleFOC Mini

* Plugs into **J7 (2×5 male)** and **J8 (1×3 male)**; VM/GND by a 5 cm wire
  pair from **J6** to its screw terminal. Keep the Mini's 100 µF side toward
  J6.
* Control: 3-PWM. TIM1 CH1/2/3 → IN1/2/3 (H1.3/5/7); EN ← PB2 (H1.9) with a
  10 k pull-down on the carrier; nSLEEP ← PB14 (H1.8), nRESET ← PB15 (H1.6)
  (both pulled up on the Mini, so they can be left as inputs until firmware
  drives them); nFAULT (H1.10) → PB12 TIM1_BKIN.
* Dead time, shoot-through protection, OCP, UVLO and thermal shutdown live in
  the DRV8313. No gate driver, gate rail or gate resistors on the carrier.
* Thermal: ≈ 1.35 W on the Mini at 1.5 A rms. Leave a copper pour under it
  and a mounting hole so the Mini can be screwed down with a thermal pad.

## 3. Current sense

* Mini OUT1 → **R_SH_A (30 mΩ)** → J2.A; OUT2 → **R_SH_B** → J2.B; OUT3 → J2.C.
  Kelvin pads to U3/U4 IN+/IN−.
* INA240A1: VS = 3V3, REF1 = 3V3, REF2 = GND → 1.65 V + 0.60 V/A; ±2.5 A.
  100 nF at VS, 10 Ω + 1 nF (sites) on the outputs.
* Ic = −Ia−Ib.

## 4. Sensing

* VBUS: 20 k (2 × 10 k) : 2.2 k → 24 V reads 2.38 V, full scale 33.3 V.
* Motor NTC on J3.5 with 10 k pull-up; board temperature from the MCU sensor.

## 5. Encoders — dual, because of the cycloidal reducer

| Port | Connector | Device | Role |
|---|---|---|---|
| I2C1 PB6/PB7 | J3 JST-XH 5P (3V3, GND, SCL, SDA, NTC) | AS5600 on the motor (as shipped) | commutation angle |
| SPI1 + CS PA4 | J4 1×6 (3V3, GND, CS, SCK, MISO, MOSI) | future MT6701 / AS5047P | replaces the AS5600 when speed or latency limits |
| SPI1 + CS PA15 | J5 1×6 (same pinout) | MT6701 / AS5047P on the **output** shaft | joint-absolute position; motor–joint difference = reducer lost motion |

AS5600's address is fixed (0x36), so the joint encoder is SPI. Pull-up sites
(4.7 k) DNP if the motor's AS5600 board has them. Firmware writes CONF (SF =
2×, FTH = 10 LSB) at boot.

## 6. CAN

* U2 SN65HVD230DR: D ← PA12, R → PA11, pin 8 to GND via 0 Ω, pin 5 NC.
  Footprint takes a TCAN332 (5 Mbps FD) later.
* 120 Ω through a 0 Ω select; populate on the two bus ends.
* CAN in / out on two JST-XH 3P (CANH, CANL, GND).
* Node ID: PC13/14/15, 2.2 k pull-downs, 0 Ω strap to 3V3 sets a bit.

## 7. Protection & safety chain

1. **Hardware**: DRV8313 OCP/UVLO/OTSD → nFAULT → **TIM1 break** forces IN1-3
   idle in one clock; EN pulled low through reset.
2. **Firmware (20 kHz)**: |I| > 2.8 A, VBUS outside 8–26 V, NTC > 100 °C,
   encoder error → disable / derate.
3. **CAN**: heartbeat timeout 100 ms → torque off.

## 8. Board outline & fab

* ~60 × 60 mm, 2-layer, Lion Circuits (1 oz is enough; 2 oz if offered).
  Bottom layer = ground pour. Mini footprint (26 × 20 mm) plus its mounting
  hole; 40 mm hole square for the motor back plate.
* Gerbers with Protel extensions, as in the Lion Circuits sample.

## 9. Spin 2 (documented, not built): discrete bridge

The AO3400s, INA240 pairing, PB13/14/15 (TIM1_CH1N-3N) and the earlier
FD6288T + 10 V rail + 22 Ω design remain valid if more than 2.5 A is ever
needed: ±5 A with 2 × 30 mΩ per phase, 16 V on AO3400 or 24 V on AOD4184.
See docs/06 and `-DBRIDGE_DISCRETE`.
