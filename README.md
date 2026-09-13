# CAN-BUS FOC Actuator

A CAN-bus FOC controller for cycloidal robot-arm joints, built as a **carrier
board for the SimpleFOC Mini** (DRV8313): on-board STM32G431, 2-shunt inline
current sensing (INA240), AS5600 motor encoder plus two SPI ports for a
joint-side absolute encoder, 1 Mbps CAN, three boards on one bus. Designed
around the parts already on hand (Robu.in invoice 3680169, connector order
ST030926127752, SimpleFOC Mini, STM32G431CBT6, ERJ8CW shunts, SS14, THT kit)
with four things left to buy.

## Spin-1 design point

| | |
|---|---|
| Power stage | SimpleFOC Mini (DRV8313) plugged into the carrier — 3-PWM + EN, nFAULT → TIM1 break |
| DC bus | **24 V** (8–26 V) |
| Phase current | **±2.5 A peak, ~1.5 A rms** continuous (DRV8313; INA240 range matches exactly) |
| Current sense | 2 × INA240A1 inline, one 30 mΩ per phase between the Mini and the motor |
| Power | MP1584EN VBUS→3.3 V direct with the CD43 3.3 µH and SS14 (no 5 V rail, no LDO) |
| MCU | STM32G431CBT6 @ 170 MHz — CORDIC, FMAC, dual ADC |
| Encoders | J3: AS5600 (I2C) + NTC on one 5-pin cable · J4/J5: SPI (MT6701 / AS5047P), motor side and output side |
| Bus | SN65HVD230 1 Mbps classic CAN (TCAN332 drop-in), node ID by solder straps |
| PCB | ~60 × 60 mm, 2-layer, Lion Circuits |
| Spin 2 | discrete bridge with the AO3400s on hand → ±5 A (documented, `-DBRIDGE_DISCRETE`) |

## Read in order

1. [`docs/01-parts-analysis.md`](docs/01-parts-analysis.md) — what the parts on hand can do, sufficiency for 3 boards, the 4-line buy list.
2. [`docs/02-hardware-architecture.md`](docs/02-hardware-architecture.md) — block diagram, power tree, Mini socket, sensing, connectors, protection.
3. [`docs/03-pin-assignment.md`](docs/03-pin-assignment.md) — LQFP-48 pin map with the Mini header mapping, conflicts found and resolved.
4. [`docs/04-firmware-capability.md`](docs/04-firmware-capability.md) — loop structure, CPU budget, dual-encoder scheme, bring-up order.
5. [`docs/05-can-protocol.md`](docs/05-can-protocol.md) — frame layout.
6. [`docs/06-spin1-decisions.md`](docs/06-spin1-decisions.md) — decisions, ranked bottleneck upgrades, encoder mounting, first-PCB checklist.

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
hardware/calc/            design_calcs.py — sense range, DRV8313 thermal, buck/SS14, cap ratings, PWM, CAN load, AS5600-through-cycloidal, spin-2 reference
hardware/pinmap/          pinmap.csv — single source of truth for the MCU pins
firmware/include/         foc_config.h — constants derived from the above (-DBRIDGE_DISCRETE for spin 2)
tools/                    check_pinmap.py · check_bom.py
```

## Next

- [ ] Confirm counts on hand: SimpleFOC Mini ≥ 3, STM32G431CBT6 ≥ 3, ERJ8CWFR030V ≥ 6, SS14 ≥ 3
- [ ] Confirm the cycloidal ratio; check whether the Minis have male or female headers
- [ ] Buy: MP1584EN ×4, male pin header strip, SMBJ26A ×4 (optional), 2-layer PCB ×5
- [ ] KiCad schematic → `hardware/kicad/`, then 2-layer layout
- [ ] Firmware: SimpleFOC-library bring-up first, then the bare-metal FOC core
