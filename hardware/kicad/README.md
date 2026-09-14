# KiCad project — CAN-BUS FOC actuator carrier (spin 1)

Open `can-foc-actuator.kicad_pro` in **KiCad 7 or newer** (files are written in
the KiCad 7 format; 8 and 9 read and upgrade it).

**Everything here is generated. Do not hand-edit the `.kicad_sch`.**
The electrical source of truth is `tools/board_design.py`; regenerate with:

```sh
python3 tools/gen_kicad.py     # writes this directory
python3 tools/check_design.py  # verifies it with kicad-cli
```

## What is in here

| File | |
|---|---|
| `can-foc-actuator.kicad_sch` | single-sheet A1 schematic, 75 components, 52 nets |
| `can-foc-actuator.kicad_pcb` | 60 × 60 mm board outline only — import the netlist, then place |
| `can-foc-actuator.kicad_pro` | project, with Default / Power (2 mm, 0.3 mm clearance) / CAN net classes |
| `lib/canfoc.kicad_sym` | the three symbols that are not in the stock libraries |
| `lib/canfoc.pretty/` | `SimpleFOC_Mini_Socket`, `MP1584_Module_4pin` |
| `sym-lib-table`, `fp-lib-table` | point the project at `lib/` |

Every other symbol and footprint comes from the stock KiCad libraries, so the
project opens on any standard install.

## How connectivity is drawn

Net labels on pins, not drawn wires. Each pin carries a label with its net name
(power pins get a short stub and a power symbol). The netlist is therefore
complete and unambiguous even though there are no long wire runs — and
`check_design.py` proves it by having KiCad export the netlist and comparing it
pin-for-pin against `board_design.py`. Spare MCU pins carry explicit
no-connect flags.

## Where the pin numbers came from

Pin numbering was taken from verified sources, not from memory:

* **STM32G431CBTx, SN65HVD230, AMS1117-3.3** — the stock KiCad symbol
  libraries the schematic itself references.
* **INA240A1D** — KiCad's upstream `Amplifier_Current` library. Worth knowing,
  because the numbering is not the obvious one:

  | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
  |---|---|---|---|---|---|---|---|
  | **IN−** | GND | REF2 | **GND** | OUT | V+ | REF1 | **IN+** |

  Pin 1 is the *inverting* input and pin 4 is a second GND. An earlier draft of
  `hardware/wiring/netlist.csv` had IN+/IN− the other way round; it is corrected.
* **SimpleFOC Mini H1/P1 pad positions** — measured out of the module's own
  EasyEDA PCB file, so the socket footprint matches the real module:
  H1 is a 2×5 on 2.54 mm with pad 1 at the origin, and P1 (OUT3, OUT2, OUT1)
  sits 17.653 mm away in Y and 1.524 mm in X.

## Before you order the PCB

1. **Measure your MP1584 module.** `MP1584_Module_4pin` uses a **17.78 mm**
   row pitch as a default — the silkscreen says `VERIFY PITCH`. Set
   `MP1584_PITCH_Y` in `tools/gen_kicad.py` to what your module actually
   measures and regenerate. This is the one dimension in the project that is
   not taken from a verified source.
2. **Check the Mini's headers.** The footprint is a socket for male pins on the
   carrier mating with the Mini's female headers. If your Mini shipped with
   male pins instead, fit female headers on the carrier — same holes.
3. `U6` pad 2 is the DRV8313's 3.3 V LDO output and is deliberately
   unconnected. Keep copper away from it.
4. Bottom layer stays a continuous ground pour; keep the two shunts Kelvin
   sensed (U3/U4 IN+/IN− leave from the inner edge of the RS1/RS2 pads).

## Next steps

- [ ] Verify the MP1584 pitch, regenerate
- [ ] Open the PCB, import the netlist (`Tools -> Update PCB from Schematic`), place, route
- [ ] Run DRC, then plot Gerbers with Protel extensions for Lion Circuits
