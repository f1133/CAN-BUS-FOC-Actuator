# CAN-BUS FOC Actuator

A field-oriented-control BLDC driver for cycloidal robot-arm joints: on-board
STM32G431, 2-shunt inline current sensing (INA240), AS5600 motor encoder plus
two SPI ports for a joint-side absolute encoder, 1 Mbps CAN, three boards on
one bus. Designed around the parts already on hand (Robu.in invoice 3680169 +
connector order ST030926127752) with the fewest additional purchases.

## Spin-1 design point

| | |
|---|---|
| DC bus | **24 V** (10–28 V) with AOD4184 TO-252 FETs; 16 V build option with AO3400 |
| Phase current | **±5 A peak, 3.5 A rms** continuous (sense-limited; FETs have 3× margin) |
| Current sense | 2 × INA240A1 inline, 15 mΩ (2 × 30 mΩ ‖) per phase |
| Power | MP1584EN 24→3.3 V direct (no 5 V rail, no LDO); 78L10 10 V gate rail |
| Gate drive | FD6288T, 22 Ω, 400 ns dead time, hardware break on nFAULT |
| MCU | STM32G431CBT6 @ 170 MHz — CORDIC, FMAC, dual ADC |
| Encoders | J3: AS5600 (I2C) + NTC on one 5-pin cable · J4/J5: SPI (MT6701 / AS5047P), motor side and output side |
| Bus | SN65HVD230 1 Mbps classic CAN (TCAN332 5 Mbps FD drop-in), node ID by solder straps |
| PCB | ~60 × 60 mm, 2-layer 2 oz, Lion Circuits |

## Read in order

1. [`docs/01-parts-analysis.md`](docs/01-parts-analysis.md) — what the parts on hand can do, sufficiency for 3 boards, the 11-line buy list.
2. [`docs/02-hardware-architecture.md`](docs/02-hardware-architecture.md) — block diagram, power tree, gate drive, sensing, connectors, protection.
3. [`docs/03-pin-assignment.md`](docs/03-pin-assignment.md) — LQFP-48 pin map, the conflicts found (PB8 = BOOT0, PB15 AF4, USART sites) and how each was resolved.
4. [`docs/04-firmware-capability.md`](docs/04-firmware-capability.md) — loop structure, CPU budget, dual-encoder scheme, bring-up order.
5. [`docs/05-can-protocol.md`](docs/05-can-protocol.md) — frame layout.
6. [`docs/06-spin1-decisions.md`](docs/06-spin1-decisions.md) — the decisions behind spin 1, ranked bottleneck upgrades, first-PCB checklist.

## Checks

```sh
python3 tools/check_pinmap.py          # 0 conflicts on hardware/pinmap/pinmap.csv
python3 tools/check_bom.py --boards 3  # shortfall table from hardware/bom/*.csv
python3 hardware/calc/design_calcs.py  # every number quoted in docs/
```

## Layout

```
docs/                     analysis, architecture, decisions
hardware/bom/             inventory.csv (what exists) · per_board.csv (what spin 1 needs)
hardware/calc/            design_calcs.py — sense range, FET thermal, buck, gate rail, cap ratings, PWM, CAN load, AS5600-through-cycloidal
hardware/pinmap/          pinmap.csv — single source of truth for the MCU pins
firmware/include/         foc_config.h — constants derived from the above (-DBRIDGE_FET_AO3400 for the 16 V build)
tools/                    check_pinmap.py · check_bom.py
```

## Next

- [ ] Confirm the cycloidal ratio and the motor's rated current
- [ ] Order the buy list (docs/01 §4)
- [ ] KiCad schematic → `hardware/kicad/`, then 2-layer layout
- [ ] Firmware: HAL init from docs/03 §4, then FOC core
