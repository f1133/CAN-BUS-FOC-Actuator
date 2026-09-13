# CAN-BUS FOC Actuator

A compact field-oriented-control BLDC driver for robot-arm joints: on-board
STM32G431, 2-shunt inline current sensing (INA240), absolute magnetic encoder,
1 Mbps CAN, three boards on one bus. Designed around the parts already on hand
(Robu.in invoice 3680169 + connector order ST030926127752 + AO3400 / ERJ8CW /
STM32G431CBT6).

## Design point

| | |
|---|---|
| DC bus | 12–18 V (4S). 24 V requires ≥ 40 V FETs — AO3400 is 30 V. |
| Phase current | ±5 A peak, 3.5 A rms continuous |
| Current sense | 2 × INA240A1 inline, 15 mΩ (2 × 30 mΩ ‖) per phase |
| PWM | TIM1, 20 kHz centre-aligned, 400 ns dead time, hardware break |
| MCU | STM32G431CBT6 @ 170 MHz — CORDIC, FMAC, dual ADC |
| Encoder | MT6701 (SSI) on 5-pin JST-XH; I2C / hall / ABZ selectable by 0 Ω jumpers |
| Bus | SN65HVD230, classic CAN 1 Mbps, node ID by solder straps |
| Size | ~50 × 50 mm, 4-layer |

## Status: analysis & architecture complete, schematic next

Read in order:

1. [`docs/01-parts-analysis.md`](docs/01-parts-analysis.md) — what the parts on
   hand can do, sufficiency for 3 boards, what is **missing** (gate driver, buck
   IC, encoder, gate resistors, TVS, 4-layer PCB).
2. [`docs/02-hardware-architecture.md`](docs/02-hardware-architecture.md) —
   block diagram, power tree, gate drive, sensing, connectors, protection.
3. [`docs/03-pin-assignment.md`](docs/03-pin-assignment.md) — full LQFP-48 pin
   map with the conflicts that were found and how each was resolved.
4. [`docs/04-firmware-capability.md`](docs/04-firmware-capability.md) — loop
   structure, CPU budget, feature list, bring-up order.
5. [`docs/05-can-protocol.md`](docs/05-can-protocol.md) — frame layout.

## Checks

```sh
python3 tools/check_pinmap.py          # 0 conflicts on hardware/pinmap/pinmap.csv
python3 tools/check_bom.py --boards 3  # shortfall table from hardware/bom/*.csv
python3 hardware/calc/design_calcs.py  # every number quoted in docs/
```

## Layout

```
docs/                     analysis & architecture
hardware/bom/             inventory.csv (what exists) · per_board.csv (what the design needs)
hardware/calc/            design_calcs.py — current-sense, thermal, buck, PWM, CAN-load maths
hardware/pinmap/          pinmap.csv — single source of truth for the MCU pins
firmware/include/         foc_config.h — constants derived from the above
tools/                    check_pinmap.py · check_bom.py
```

## Next

- [ ] Confirm quantities of AO3400, ERJ8CWFR030V, STM32G431CBT6
- [ ] Order the missing parts (docs/01 §4)
- [ ] KiCad schematic → `hardware/kicad/`
- [ ] Firmware: HAL init from docs/03 §4, then FOC core
