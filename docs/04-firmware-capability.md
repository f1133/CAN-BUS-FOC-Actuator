# 04 — Firmware capability

What the STM32G431CBT6 lets this board do, with CPU budgets, and how the
firmware is structured. The MCU is over-provisioned for the job by roughly
10×, which is what makes the advanced features below realistic.

## 1. Why the G431 is the right part

| Feature | Use in this design | Payoff |
|---|---|---|
| Cortex-M4F @ 170 MHz, FPU | all control math in `float` | no fixed-point bookkeeping |
| **CORDIC** co-processor | `sin/cos(θe)` for Park/inverse-Park, `atan2` for observers | ~20 cycles vs ~150 for a software sin/cos; the whole Park transform becomes ~0.2 µs |
| **FMAC** | optional hardware IIR on velocity / notch on Iq | offloads filtering from the ISR |
| 2 × 12-bit ADC, 4 MSPS, injected groups, dual-simultaneous, hardware oversampling | Ia/Ib sampled at the same instant on the TIM1 trigger; 16× oversampling gives ~14 effective bits on VBUS/NTC | zero-skew current sampling; ISR starts with fresh data in the JDR registers |
| TIM1 advanced timer: 6 complementary outputs, dead-time generator, 2 break inputs, repetition counter, TRGO2 | PWM + ADC trigger + hardware trip | the safety chain never touches the CPU |
| FDCAN (classic + FD) with 3 Rx FIFOs / filters | bus | message filtering by node ID in hardware |
| 128 KB flash / 32 KB SRAM (+ 10 KB CCM-SRAM) | firmware ~40 KB, calibration tables, CAN stack | room for anti-cogging LUT (4 KB) and a bootloader |
| 3 op-amps, 4 comparators, DAC | COMP → BKIN2 for VBUS over-voltage trip; DAC for debug scope out (if pins were free) | |
| USB-less LQFP-48 | — | PA11/PA12 are free for CAN |

## 2. Control loop structure & CPU budget

Everything is triggered from TIM1 so all loops are phase-locked to the PWM.

```
TIM1 update (20 kHz, counter at top) ──► ADC1/2 injected (Ia, Ib, simultaneous)
                                          │  ~1.5 µs conversion + sequencer
                                          ▼
                              ADC1_2 JEOS ISR   ← highest priority
                              ┌────────────────────────────────────────┐
                              │ read Ia, Ib; Ic = -Ia-Ib               │
                              │ θm: AS5600 (1 kHz I2C) + ω·Δt extrap.  │
                              │ θe = (θm - θoffset) * Pp               │
                              │ CORDIC sin/cos θe                      │
                              │ Clarke → Park → Id, Iq                 │
                              │ PI(Id→0)  PI(Iq→Iq*)  + decoupling     │
                              │ inverse Park → Vα, Vβ                  │
                              │ SVPWM → CCR1..3  (written before next  │
                              │        update; effective at next top)  │
                              │ overcurrent / VBUS / fault checks      │
                              └────────────────────────────────────────┘
                              ≈ 2.5–4 µs measured on G4 class parts with CORDIC
                              = 5–8 % of the 50 µs period

every 5th current ISR (4 kHz): velocity loop  (PI + optional FMAC IIR)     ~1 µs
every 20th          (1 kHz):   position loop, CAN feedback frame, VBUS/NTC ~3 µs
main loop:                     CAN Rx, commander UART, LED, parameter store
```

CPU load at 20 kHz ≈ 10 %; at 40 kHz PWM ≈ 20 %. There is room to double the
current-loop rate, run a flux observer alongside the encoder, or add an
impedance controller.

## 3. What it can do

| Capability | Status | Notes |
|---|---|---|
| Sensored FOC (current / velocity / position) | core | 2-shunt inline, 20 kHz. Through a ×15 cycloidal, 360 °/s at the joint is 900 rpm / 105 Hz electrical → ~10 AS5600 reads per electrical cycle: fine for arm speeds; the J4 SPI encoder is the upgrade beyond that. |
| Torque control from CAN at 1 kHz | core | the robot-arm mode: host runs the arm dynamics, joints run torque + local impedance |
| Impedance / compliance mode (`τ = Kp(θ*−θ) + Kd(ω*−ω) + τff`) | core | all five params in one 8-byte CAN frame (docs/05) |
| Absolute position at power-on | core | Output-side SPI encoder on J5 (14-bit, on the joint shaft after the cycloidal). The motor-side AS5600 wraps every 1/ratio of a joint turn, so it cannot provide this alone; without J5 fitted, a homing move is required at boot. |
| Dual-encoder actuator | core | commutation from the motor-side AS5600 (I2C at 1 kHz, angle extrapolated with ω at 20 kHz); position loop closed on the J5 joint encoder; motor–joint difference = reducer lost motion / compliance estimate |
| Encoder offset & pole-pair auto-calibration | core | align routine, stores to flash page |
| Anti-cogging | planned | 1024-entry torque LUT per motor, learned once |
| Field weakening | planned | free with the Id loop; useful only for high-speed joints |
| Sensorless (flux observer) fallback | possible | CORDIC atan2 makes it cheap; only as a diagnostic since a robot arm needs absolute angle |
| Motor thermal model | core | NTC + I²t estimator; derates Iq limit |
| Hardware trip on nFAULT | core | TIM1 break, sub-microsecond |
| Firmware update over CAN | planned | 16 KB bootloader region; 128 KB flash allows A/B |
| SimpleFOC-library compatibility | supported | the pin map matches what `SimpleFOC` `BLDCDriver6PWM` + `InlineCurrentSense` expect on STM32; a SimpleFOC build is the quickest bring-up path before the bare-metal firmware |

## 4. Sampling strategy with inline shunts

Because the INA240s are inline, phase current is valid at every point of the PWM
cycle. The ISR samples at the counter top (centre of the zero vector), which is
also the point of least switching noise. No minimum-pulse or duty-window logic
is needed — the main reason inline sensing is worth the two amplifiers.

Current reconstruction: `Ic = -(Ia + Ib)`. There is no 3rd-shunt option on this board (8 INA240 for 3 boards; PA7 is SPI1_MOSI). Accuracy at high modulation is adequate for the ±5 A / 2.7 mA-LSB design point.

## 5. Timing constants (also in `firmware/include/foc_config.h`)

| Constant | Value | Derivation |
|---|---|---|
| `SYSCLK` | 170 MHz | 8 MHz HSE, PLLM 2, PLLN 85, PLLR 2 |
| `PWM_FREQ` | 20 000 Hz | audible-noise floor; 40 kHz available |
| `TIM1_ARR` | 4250 | 170 MHz / (2 × 20 kHz), centre-aligned |
| `TIM1_DTG` | 68 | 400 ns / 5.88 ns |
| `CURRENT_LOOP_HZ` | 20 000 | one per PWM period |
| `VELOCITY_DIV` | 5 | 4 kHz |
| `POSITION_DIV` | 20 | 1 kHz |
| `ADC_V_PER_LSB` | 3.3 / 4096 = 0.8057 mV | |
| `ISENSE_V_PER_A` | 0.30 V/A | 15 mΩ × 20 |
| `ISENSE_OFFSET_V` | 1.65 V | REF = VS/2 (auto-calibrated at boot with the bridge disabled) |
| `I_MAX_A` | 5.0 | INA240 output swing |
| `I_TRIP_A` | 5.5 | software trip |
| `ENC_M_READ_HZ` | 1000 | AS5600 I2C read rate; θ extrapolated between reads |
| `AS5600_CONF_SF` | 2× | 0.29 ms filter latency instead of the default 2.2 ms |
| `GEAR_RATIO` | cycloidal ratio | joint = motor / ratio when J5 is not fitted |
| `VBUS_V_PER_LSB` | 0.8057 mV × 22.2 / 2.2 = 8.13 mV | 20 k : 2.2 k divider |
| `CAN_BITRATE` | 1 000 000 | SN65HVD230 limit |
| `CAN_HEARTBEAT_TIMEOUT_MS` | 100 | |

## 6. Bring-up order (what to test first)

1. Power only: 5 V, 3V3, 10 V rails; MCU blink + SWD + UART.
2. CAN loopback then bus with a USB-CAN dongle at 1 Mbps.
3. AS5600 over I2C (write CONF SF = 2×), verify 12-bit angle vs hand rotation; then the J5 SPI encoder if fitted.
4. INA240 offsets with bridge disabled (expect 1.65 V ± 5 mV).
5. Open-loop V/f spin at 2 V, 1 A limit; watch phase currents on the debug
   stream — this validates gate polarity, dead-time and current sign.
6. Encoder alignment routine → sensored FOC torque mode.
7. Velocity → position → impedance.
8. Fault injection: pull nFAULT low, expect outputs off within one PWM period.
