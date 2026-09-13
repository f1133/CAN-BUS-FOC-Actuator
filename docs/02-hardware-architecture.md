# 02 — Hardware architecture (spin 1)

One board = one joint. Three identical boards on one CAN bus.

```
  J1 JST-VH 2P
  VBUS 24 V ──┬── SMBJ26A ──┬── 2×470 µF 50 V ──┬────────────────────────────────┐
  GND ────────┤             │                    │                                │
              │      ┌──────┴──────┐      ┌──────┴──────┐                   ┌─────┴─────┐
              │      │ U7 MP1584EN │      │ U8 78L10    │                   │ 3× half-  │  J2 JST-XH 3P
              │      │ 24 → 3.3 V  │      │ 10 V gate   │                   │ bridge    │──► A B C
              │      │ L1 3.3 µH   │      │ rail ~7 mA  │                   │ 6×AOD4184 │
              │      │ SS34, 100k  │      └──────┬──────┘                   └──┬──┬─────┘
              │      └──────┬──────┘             │ VCC                          │  │
              │            3V3            ┌──────┴────────────┐           2×15 mΩ inline shunt
              │             │             │ U6 FD6288T        │                │  │
              │  ┌──────────┴───────────┐ │ 3-ph gate driver  │        ┌───────┴──┴───────┐
              │  │ U1 STM32G431CBT6     │ │ bootstrap 3×1 µF  │        │ U3 U4 INA240A1   │
              │  │ TIM1 CH1-3/CH1N-3N ──┼─► HIN/LIN ×6        │        │ ×20, REF = VS/2  │
              │  │ PB2  DRV_EN ─────────┼─► EN                │        │                  │
              │  │ PB12 TIM1_BKIN ◄─────┼── nFAULT            │        │                  │
              │  │ PA0 ADC1_IN1 ◄───────┼──┼──────────────────┼────────┤ ISENSE_A         │
              │  │ PA1 ADC2_IN2 ◄───────┼──┼──────────────────┼────────┤ ISENSE_B         │
              │  │ PA2 ADC1_IN3 ◄─ VBUS 20k:2.2k              │        └──────────────────┘
              │  │ PA3 ADC1_IN4 ◄─ NTC (J3.5) 10k pull-up
              │  │ PB6/PB7 I2C1 ────────┼── J3 JST-XH 5P: 3V3 GND SCL SDA NTC  (AS5600 on motor)
              │  │ PA4 CS_A, PA15 CS_B  │
              │  │ PA5/6/7 SPI1 ────────┼── J4 SPI_A 1×6 (motor-side upgrade)   J5 SPI_B 1×6 (output-side abs. encoder)
              │  │ PA11/12 FDCAN1 ──────┼── U2 SN65HVD230 (TCAN332-compatible) ── CANH/CANL, 120 Ω via 0R
              │  │ PB3/4 USART2, PA13/14 SWD, PB9 LED, PC13-15 ID straps, PF0/1 HSE 8 MHz
              │  └──────────────────────┘
```

## 1. Power tree

| Rail | Source | Load | Notes |
|---|---|---|---|
| VBUS 24 V (10–28 V) | J1 (keyed JST-VH; no reverse-polarity FET) | bridge, buck, 78L10 | SMBJ26A at the connector. 2 × 470 µF 50 V. **Only 50 V / 250 V ceramics on this rail** — the 10 µF are 25 V. 100 nF 250 V at each half-bridge, 1 µF 50 V at the MP1584 input. |
| 10 V gate | U8 78L10 from VBUS, 100 nF in/out + 1 µF | FD6288T VCC, ~7 mA | ≤ 10 V keeps a 2 V margin under the AO3400's ±12 V Vgs limit if the 16 V build is ever populated; AOD4184 (±20 V) doesn't care. Dropout OK down to 12 V bus. |
| 3V3 | U7 MP1584EN, L1 CD43 3.3 µH, SS34, RFREQ 100 k (~1 MHz), FB 10 k + 4.7 k / 4.7 k, 10 µF + 1 µF out | MCU, INA240 ×2, CAN, AS5600, SPI encoders, LEDs (~100 mA) | No 5 V rail, no LDO. VDDA through a 0 Ω/ferrite site + 1 µF + 100 nF; VREF+ = VDDA with 1 µF. |

## 2. Gate driver — FD6288T (EG2133 as alternate)

* Three bootstrap half-bridges, integrated bootstrap diodes, 3.3 V inputs,
  shoot-through lockout with ~200 ns internal dead time.
* HIN1-3 ← PA8/PA9/PA10 (TIM1_CH1-3); LIN1-3 ← PB13/PB14/PB15 (CH1N-3N).
  Input polarity is a firmware bit (`TIM1_CCER.CCxNP`), so an active-low LIN
  variant also works.
* Bootstrap caps 1 µF 50 V (≥ 80 nF needed for 40 nC; 40 mV droop/cycle).
* Gate resistors 22 Ω. nFAULT → PB12 TIM1_BKIN, 10 k pull-up. EN → PB2, 10 k
  pull-**down**.

## 3. Power stage — 6 × AOD4184 (TO-252)

* Each half-bridge: 100 nF 250 V across VBUS–GND within 3 mm of the FETs;
  high-side drain tab on the VBUS pour, low-side source into the bottom-layer
  ground pour through a via field. At 3.5 A rms: 0.44 W conduction + 1.3 W
  switching across the six devices.
* 16 V build: AO3400A on a SOT-23 footprint, same driver and rail; bus ≤ 18 V.
* RC snubber site (10 Ω + 1 nF, DNP) across each low-side FET.

## 4. Current sense

* Phases A and B: 2 × ERJ8CWFR030V in parallel (15 mΩ) in the motor lead
  between the half-bridge output and J2. Kelvin pads to U3/U4 IN+/IN−.
* INA240A1: VS = 3V3, REF1 = 3V3, REF2 = GND → 1.65 V + 0.30 V/A. 100 nF at
  VS, 10 Ω + 1 nF on the output to the ADC pin.
* Phase C reconstructed (Ic = −Ia−Ib). No 3rd-shunt site.

## 5. Sensing

* VBUS: 20 k (2 × 10 k) : 2.2 k → 24 V reads 2.38 V, full scale 33.3 V.
* Motor NTC (MF52E103, 10 k, B ≈ 3950): 10 k pull-up to 3V3, on J3 pin 5 with
  the thermistor glued into the winding at the motor end.
* Board temperature: MCU internal sensor.

## 6. Encoders — dual, because of the cycloidal reducer

| Port | Connector | Device | Role |
|---|---|---|---|
| I2C1 PB6/PB7 | J3 JST-XH 5P (3V3, GND, SCL, SDA, NTC) | AS5600 on the motor (as shipped) | commutation angle; wraps every 1/ratio joint turn |
| SPI1 + CS PA4 | J4 1×6 (3V3, GND, CS, SCK, MISO, MOSI) | future MT6701 (SSI) / AS5047P | replaces the AS5600 when speed or latency becomes limiting |
| SPI1 + CS PA15 | J5 1×6 (same pinout) | MT6701 / AS5047P on the **output** shaft | joint-absolute position at power-on; motor–joint difference = reducer lost motion |

AS5600 notes: address is fixed (0x36) so a second one cannot share the bus —
that is why the joint encoder is SPI. I2C pull-ups on the motor's AS5600 board
(4.7 k sites on the PCB, DNP). Firmware writes CONF (SF = 2×, FTH = 10 LSB) at
boot to cut the default 2.2 ms filter latency to 0.29 ms.

## 7. CAN

* U2 SN65HVD230DR: D ← PA12, R → PA11, pin 8 (RS) to GND through 0 Ω =
  high-speed mode; pin 5 (Vref) NC. The same footprint takes a **TCAN332**
  (pin 8 = STB → GND is normal mode, pin 5 NC) for 5 Mbps FD later.
* 120 Ω through a 0 Ω select; populate on the two bus ends only.
* Bus in/out on two 3-pin JST-XH (CANH, CANL, GND) for daisy-chaining.
* Node ID: PC13/14/15, 2.2 k pull-downs, 0 Ω strap to 3V3 sets a bit → 0–7.

## 8. Protection & safety chain

1. **Hardware**: FD6288T shoot-through lockout → TIM1 dead time → nFAULT →
   **TIM1 break** forces all six outputs to idle in one clock, no CPU.
2. **Firmware (20 kHz)**: |I| > 5.5 A, VBUS outside 10–28 V, NTC > 100 °C,
   encoder error, AS5600 magnet-status bits → disable / derate.
3. **CAN**: heartbeat timeout 100 ms → torque off.
4. **DRV_EN** low through reset (pull-down); asserted only after self-test.

## 9. Board outline & fab

* ~60 × 60 mm, 2-layer, 2 oz, 1.6 mm, Lion Circuits. Bottom layer = ground
  pour, broken only by short jumpers under the MCU. Mounting holes on a 40 mm
  square to bolt to the motor back plate; J5 cable runs to the output-shaft
  encoder.
* Gerbers with Protel extensions (`.GTL .GBL .GTS .GBS .GTO .GBO .GKO .drl`),
  as in the Lion Circuits sample.
