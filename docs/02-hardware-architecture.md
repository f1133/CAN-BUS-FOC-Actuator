# 02 — Hardware architecture

One board = one joint. Three identical boards on one CAN bus.

```
                     ┌───────────────────────────────────────────────────────────────┐
  J1 JST-VH 2P       │                                                               │
  VBUS 12–18 V ──►──┬┤ Q7 AO3481 (rev-pol) ─┬─ TVS ─┬─ 2×470 µF ─┬─────────────────┐ │
  GND ───────────────┤                      │       │            │                 │ │
                     │            ┌─────────┴───┐    │  ┌─────────┴────────┐        │ │
                     │            │ U7 buck     │    │  │ U8 78L10 / zener │        │ │
                     │            │ 24→5 V      │    │  │ 10 V gate rail   │        │ │
                     │            │ L1 3.3 µH   │    │  └─────────┬────────┘        │ │
                     │            └─────┬───────┘    │            │                 │ │
                     │                  5 V          │            │ VCC             │ │
                     │            ┌─────┴───────┐    │  ┌─────────┴────────┐  ┌─────┴─────┐
                     │            │ U5 AMS1117  │    │  │ U6 FD6288T       │  │ 3× half-  │  J2 JST-XH 3P
                     │            │ 5→3.3 V     │    │  │ 3-ph gate driver │──│ bridge    │──► A B C
                     │            └─────┬───────┘    │  │ bootstrap ×3     │  │ 6× AO3400 │
                     │                  3V3          │  └──▲──▲──▲──▲──────┘  └──┬──┬─────┘
                     │                  │            │     │  │  │  │            │  │
                     │   ┌──────────────┴─────────┐  │  6× PWM  EN nFAULT   2× 15 mΩ inline shunt
                     │   │ U1 STM32G431CBT6       │  │     │  │  │  │            │  │
                     │   │  TIM1 CH1-3 + CH1N-3N ─┼──┼─────┘  │  │  │      ┌─────┴──┴─────┐
                     │   │  PB2  DRV_EN ──────────┼──┼────────┘  │  │      │ U3 U4 INA240 │
                     │   │  PB12 TIM1_BKIN ◄──────┼──┼───────────┘  │      │ ×20, REF=VS/2│
                     │   │  PA0 ADC1_IN1 ◄────────┼──┼──────────────┼──────┤ ISENSE_A     │
                     │   │  PA1 ADC2_IN2 ◄────────┼──┼──────────────┼──────┤ ISENSE_B     │
                     │   │  PA2 ADC1_IN3 ◄─ VBUS/10 (20k:2.2k)      │      └──────────────┘
                     │   │  PA3 ADC1_IN4 ◄─ NTC 10k/10k              │
                     │   │  PA4/5/6 SPI1 ─────────┼── J3 JST-XH 5P encoder (MT6701 SSI)
                     │   │  PB6/7 I2C1 ───────────┼── (alt encoder via 0R select)
                     │   │  PA11/12 FDCAN1 ───────┼── U2 SN65HVD230 ── CANH/CANL (+120 Ω via 0R)
                     │   │  PB3/4 USART2 ─────────┼── debug header
                     │   │  PA13/14 SWD ──────────┼── SWD header
                     │   │  PC13/14/15 ID0-2 ◄────┼── 0R straps
                     │   │  PF0/PF1 HSE 8 MHz     │
                     │   └────────────────────────┘
                     └───────────────────────────────────────────────────────────────┘
```

## 1. Power tree

| Rail | Source | Load | Notes |
|---|---|---|---|
| VBUS 12–18 V (24 V with 40 V FETs) | J1 via Q7 (AO3481 reverse-polarity P-FET, gate to GND through 10 k) | bridge, buck, gate-rail regulator | TVS SMBJ18A/26A right at the connector. 2 × 470 µF 50 V + 3 × 100 nF at each half-bridge. |
| 10 V gate rail | 78L10 (or 10 V zener + 1 kΩ) from VBUS | FD6288T VCC, ~2 mA avg | Chosen ≤ 10 V because **AO3400 Vgs abs-max is ±12 V**. Gate driver UVLO (~8 V) stays satisfied. 1 µF + 100 nF at VCC. |
| 5 V | U7 MP2451/MP1584 buck, L1 = CD43 3.3 µH, 10 µF in / 10 µF + 1 µF out | AMS1117 only | ≈ 1.4 MHz. DCM at the 150 mA logic load; peak inductor current 0.58 A < 1 A Isat. |
| 3V3 | U5 AMS1117-3.3, 10 µF out | MCU, INA240 ×2, CAN, encoder, LED | 0.26 W dissipation. VDDA fed through a ferrite/10 Ω + 1 µF + 100 nF; VREF+ tied to VDDA with 1 µF. |

Why not one 12 V buck feeding both? The single 3.3 µH per board is sized for the
5 V converter; a 24→12 V buck at 3.3 µH would run ΔI > 3 A. And the gate rail
draws ~1 mA, so a linear regulator is the right tool.

## 2. Gate driver — FD6288T (primary) / EG2133 (alternate)

* Three bootstrap half-bridges, integrated bootstrap diodes, 3.3 V-compatible
  inputs, internal shoot-through lockout + ~200 ns internal dead time.
* Inputs: HIN1-3 ← PA8/PA9/PA10 (TIM1_CH1-3), LIN1-3 ← PB13/PB14/PB15
  (TIM1_CH1N-3N). Polarity is a firmware bit (`TIM1_CCER.CCxNP`), so either an
  active-high or active-low LIN driver drops in.
* Bootstrap caps: 1 µF 50 V X7R (need ≥ 18 nF; 1 µF gives ~10 mV droop/cycle).
* Gate resistors: 22 Ω on-board (buy). 120 Ω from stock works at 20 kHz with
  ~0.3 W extra loss per FET.
* nFAULT (open-drain, some variants) → PB12 TIM1_BKIN with 10 k pull-up.
  EN/SD → PB2 with 10 k pull-**down** so the bridge is off during reset.

Premium alternative: **DRV8350H** (TI, 9–100 V, IDRIVE-settable, VDS
overcurrent → nFAULT). Its internal gate LDO is ~11–12 V, uncomfortably close to
the AO3400 ±12 V limit; use it only if you also move to a 40/60 V FET.

## 3. Power stage

* Q1–Q6 AO3400A in SOT-23. Each half-bridge: 100 nF ceramic across VBUS–GND
  within 3 mm of the FETs, high-side drain and low-side source on wide 2 oz
  pours, thermal vias under each FET tab.
* Phase current at 3.5 A rms → 1.5 W conduction + 0.5 W switching across the six
  devices. Spread them over ≥ 6 cm² of pour.
* RC snubber footprint (10 Ω + 1 nF, DNP) across each low-side FET for
  ringing control at 24 V.

## 4. Current sense

* Phases A and B carry **2 × ERJ8CWFR030V in parallel (15 mΩ)** in series with
  the motor lead, between the half-bridge output and J2.
* U3/U4 INA240A1: IN+/IN− kelvin-connected to the shunt pads; VS = 3V3,
  REF1 = 3V3, REF2 = GND → output = 1.65 V + 0.3 V/A. 100 nF at VS, 10 Ω +
  1 nF RC on the output to the ADC pin (fc ≈ 16 MHz — only for ESD/edge
  rounding; the amp's 400 kHz bandwidth dominates).
* Phase C reconstructed in firmware. Footprint for a 3rd INA240 + shunt pair on
  phase C → PA7 (ADC2_IN4), DNP.

## 5. Sensing

* VBUS: 20 k (2 × 10 k) : 2.2 k → 24 V reads 2.38 V; full scale 33.3 V.
  ADC1_IN3, regular group, 1 kHz.
* Motor NTC (MF52E103 10 k, B≈3950): 10 k pull-up to 3V3, ADC1_IN4. Wire the
  NTC into the motor windings; bring it in on a 2-pin JST-XH (use two of the
  spare 3-pin XH housings) or on spare pins of the encoder cable.
* Board temperature: MCU internal sensor (ADC1_IN16) — no extra parts.

## 6. Encoder connector J3 (JST-XH 5P)

| Pin | Net | SSI (MT6701 / AS5047 3-wire) | I2C (AS5600) | Hall / ABZ |
|---|---|---|---|---|
| 1 | 3V3 | VDD | VDD | VDD |
| 2 | GND | GND | GND | GND |
| 3 | ENC_S1 | CSN ← PA4 | SCL ← PB6 (via 0R) | H1/A → PB5 (via 0R) |
| 4 | ENC_S2 | CLK ← PA5 | SDA ↔ PB7 (via 0R) | H2/B → PB10 (via 0R) |
| 5 | ENC_S3 | DO → PA6 | — | H3/Z → PB11 (via 0R) |

Default population: SSI (PA4/PA5/PA6 straight through). The 0 Ω jumpers in the
BOM (44 on hand) select the alternate routing; only one set is populated.

## 7. CAN

* U2 SN65HVD230DR: D ← PA12 (FDCAN1_TX), R → PA11 (FDCAN1_RX), RS pin to GND
  through 10 k (slope control) — or 0 Ω for full 1 Mbps edge rate.
* 120 Ω termination through a 0 Ω select jumper; populate only on the two bus
  ends.
* CANH/CANL on the two 3-pin JST-XH (in + daisy-chain out) or a 4-pin header;
  10 3-pin XH are on hand so use two per board.
* Node ID: PC13/PC14/PC15 with 10 k pull-downs, 0 Ω to 3V3 to set a bit → IDs
  0–7. No reflashing to change a joint's address.

## 8. Protection & safety chain

1. **Hardware**: FD6288T shoot-through lockout → TIM1 dead-time (400 ns) →
   driver nFAULT / VBUS-overvoltage comparator → **TIM1 break input** forces
   all six outputs to their idle state in one clock, no CPU involvement.
2. **Firmware (20 kHz)**: |Ia|,|Ib|,|Ic| > 5.5 A → disable; VBUS outside
   10–30 V → disable; NTC > 100 °C → derate; encoder CRC/magnet-loss → disable.
3. **CAN**: heartbeat timeout (default 100 ms) → torque off, brake mode
   selectable.
4. **DRV_EN** defaults low at reset via pull-down; the MCU must actively assert
   it after self-test.

## 9. Board outline & fab

* Target ~50 × 50 mm, 4-layer (SIG / GND / PWR / SIG), 2 oz outer copper,
  1.6 mm. Mounting holes on a 40 mm square so it bolts to a NEMA17-class motor
  back plate; magnet on the shaft, MT6701 on a small daughter board through the
  centre hole.
* Export Gerbers with Protel extensions (`.GTL .GBL .GTS .GBS .GTO .GBO .GKO
  .drl`) — matches the Lion Circuits sample; JLCPCB accepts the same.
