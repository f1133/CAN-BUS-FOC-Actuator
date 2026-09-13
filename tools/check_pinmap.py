#!/usr/bin/env python3
"""
Mechanical pin-conflict check for hardware/pinmap/pinmap.csv against the
STM32G431CBT6 (LQFP-48) alternate-function table.

Checks:
  1. every pin used exists on the LQFP-48 package
  2. no pin is assigned twice
  3. every AF claim (pin, peripheral signal, AF number) is a legal mapping
     per RM0440 / DS12589 for this device
  4. every analog claim maps to the right ADC channel
  5. the peripheral signals that must coexist (TIM1 x6, FDCAN1 x2, SPI1 x2,
     USART2 x2, I2C1 x2, ADC1/ADC2 pairs) are all present exactly once
  6. no signal is on a reset-sensitive / boot pin unless flagged

Exit 0 == no conflicts.  Run: python3 tools/check_pinmap.py
"""
import csv
import sys
from collections import Counter
from pathlib import Path

PINMAP = Path(__file__).resolve().parents[1] / "hardware" / "pinmap" / "pinmap.csv"

# STM32G431CBT6 LQFP-48 bonded GPIOs (DS12589 rev 6, Table 13)
LQFP48_PINS = {
    *(f"PA{i}" for i in range(16)),
    *(f"PB{i}" for i in range(16)),
    "PC13", "PC14", "PC15",
    "PF0", "PF1",
    "PG10",
}

# Legal alternate-function mappings on this device (subset relevant to design).
# (pin, signal) -> AF number.  Source: DS12589 Tables 14-16 (AF0..AF15).
AF_TABLE = {
    # TIM1 advanced timer
    ("PA8", "TIM1_CH1"): 6, ("PA9", "TIM1_CH2"): 6, ("PA10", "TIM1_CH3"): 6,
    ("PA11", "TIM1_CH1N"): 6, ("PA7", "TIM1_CH1N"): 6, ("PB13", "TIM1_CH1N"): 6, ("PC13", "TIM1_CH1N"): 4,
    ("PA12", "TIM1_CH2N"): 6, ("PB0", "TIM1_CH2N"): 6, ("PB14", "TIM1_CH2N"): 6,
    ("PB1", "TIM1_CH3N"): 6, ("PB15", "TIM1_CH3N"): 4, ("PF0", "TIM1_CH3N"): 6,
    ("PA6", "TIM1_BKIN"): 6, ("PA14", "TIM1_BKIN"): 6, ("PA15", "TIM1_BKIN"): 9,
    ("PB8", "TIM1_BKIN"): 12, ("PB10", "TIM1_BKIN"): 12, ("PB12", "TIM1_BKIN"): 6, ("PC13", "TIM1_BKIN"): 2,
    ("PA11", "TIM1_BKIN2"): 12, ("PC3", "TIM1_BKIN2"): 6,
    # FDCAN1
    ("PA11", "FDCAN1_RX"): 9, ("PB8", "FDCAN1_RX"): 9,
    ("PA12", "FDCAN1_TX"): 9, ("PB9", "FDCAN1_TX"): 9,
    # SPI1
    ("PA5", "SPI1_SCK"): 5, ("PB3", "SPI1_SCK"): 5,
    ("PA6", "SPI1_MISO"): 5, ("PB4", "SPI1_MISO"): 5,
    ("PA7", "SPI1_MOSI"): 5, ("PB5", "SPI1_MOSI"): 5,
    ("PA4", "SPI1_NSS"): 5, ("PA15", "SPI1_NSS"): 5,
    # USART1 / USART2 / LPUART1
    ("PA9", "USART1_TX"): 7, ("PB6", "USART1_TX"): 7,
    ("PA10", "USART1_RX"): 7, ("PB7", "USART1_RX"): 7,
    ("PA2", "USART2_TX"): 7, ("PB3", "USART2_TX"): 7, ("PA14", "USART2_TX"): 7,
    ("PA3", "USART2_RX"): 7, ("PB4", "USART2_RX"): 7, ("PA15", "USART2_RX"): 7,
    ("PA2", "LPUART1_TX"): 12, ("PB11", "LPUART1_TX"): 8,
    ("PA3", "LPUART1_RX"): 12, ("PB10", "LPUART1_RX"): 8,
    # I2C1
    ("PA13", "I2C1_SCL"): 4, ("PA15", "I2C1_SCL"): 4, ("PB6", "I2C1_SCL"): 4, ("PB8", "I2C1_SCL"): 4,
    ("PA14", "I2C1_SDA"): 4, ("PB7", "I2C1_SDA"): 4, ("PB9", "I2C1_SDA"): 4,
    # SYS
    ("PA13", "SYS_SWDIO"): 0, ("PA14", "SYS_SWCLK"): 0, ("PB3", "SYS_SWO"): 0,
}

# ADC channel map (RM0440 §21.4.x, DS12589 pin definitions)
ADC_TABLE = {
    "ADC1_IN1": "PA0", "ADC1_IN2": "PA1", "ADC1_IN3": "PA2", "ADC1_IN4": "PA3",
    "ADC1_IN5": "PB14", "ADC1_IN11": "PB12", "ADC1_IN12": "PB1", "ADC1_IN14": "PB11", "ADC1_IN15": "PB0",
    "ADC2_IN1": "PA0", "ADC2_IN2": "PA1", "ADC2_IN3": "PA6", "ADC2_IN4": "PA7",
    "ADC2_IN12": "PB2", "ADC2_IN13": "PA5", "ADC2_IN14": "PB11", "ADC2_IN15": "PB15", "ADC2_IN17": "PA4",
}

# Signals that the design *requires*, with the number of pins each occupies.
REQUIRED_COUNT = {"HSE": 2}   # OSC_IN + OSC_OUT
REQUIRED = [
    "TIM1_CH1", "TIM1_CH2", "TIM1_CH3", "TIM1_CH1N", "TIM1_CH2N", "TIM1_CH3N", "TIM1_BKIN",
    "FDCAN1_RX", "FDCAN1_TX",
    "SPI1_SCK", "SPI1_MISO", "SPI1_MOSI",
    "USART2_TX", "USART2_RX",
    "I2C1_SCL", "I2C1_SDA",
    "SYS_SWDIO", "SYS_SWCLK",
    "HSE", "NRST", "BOOT0",
]

# Pins with reset-time or boot-time special behaviour
BOOT_SENSITIVE = {"PB8": "BOOT0 sampled at reset — an idle-high signal here enters the ROM bootloader"}
RESET_JTAG = {"PA13", "PA14", "PA15", "PB3", "PB4"}  # JTAG/SWD default at reset


def main() -> int:
    rows = list(csv.DictReader(PINMAP.open()))
    errors, warnings = [], []

    # 1 & 2
    pins = [r["pin"] for r in rows]
    for p in pins:
        if p not in LQFP48_PINS:
            errors.append(f"{p}: not bonded on LQFP-48")
    for p, n in Counter(pins).items():
        if n > 1:
            errors.append(f"{p}: assigned {n} times")

    seen_signals = Counter()
    for r in rows:
        pin, sig, mode, per, af = r["pin"], r["signal"], r["mode"], r["peripheral"], r["af"]
        if per:
            seen_signals[per] += 1

        # 3
        if mode == "af":
            key = (pin, per)
            if key not in AF_TABLE:
                errors.append(f"{pin}: {per} is not a legal alternate function on this pin")
            elif str(AF_TABLE[key]) != af:
                errors.append(f"{pin}: {per} needs AF{AF_TABLE[key]}, pinmap says AF{af or '?'}")
        # 4
        elif mode == "analog":
            if per not in ADC_TABLE:
                errors.append(f"{pin}: unknown ADC channel {per}")
            elif ADC_TABLE[per] != pin:
                errors.append(f"{pin}: {per} lives on {ADC_TABLE[per]}, not {pin}")
        elif mode in ("gpio_out", "gpio_in", "osc", "reset", "boot"):
            pass
        else:
            errors.append(f"{pin}: unknown mode '{mode}'")

        # 6
        if pin in BOOT_SENSITIVE and mode not in ("boot",):
            errors.append(f"{pin}: {BOOT_SENSITIVE[pin]} (signal {sig})")
        if pin in RESET_JTAG and mode == "af" and not per.startswith("SYS_"):
            warnings.append(f"{pin}: {sig} on a JTAG-default pin — firmware must disable JTAG (SWD-only) before use; fine.")

    # 5
    for sig in REQUIRED:
        n, want = seen_signals.get(sig, 0), REQUIRED_COUNT.get(sig, 1)
        if n != want:
            errors.append(f"required signal {sig} appears {n} times (need exactly {want})")

    # Simultaneous-sampling sanity: ISENSE_A must be on ADC1 and ISENSE_B on ADC2
    by_signal = {r["signal"]: r for r in rows}
    a, b = by_signal.get("ISENSE_A"), by_signal.get("ISENSE_B")
    if not (a and b and a["peripheral"].startswith("ADC1") and b["peripheral"].startswith("ADC2")):
        errors.append("ISENSE_A/ISENSE_B must be on ADC1/ADC2 respectively for dual-simultaneous injected sampling")

    used = set(pins)
    spare = sorted(LQFP48_PINS - used)
    print(f"pinmap: {len(rows)} pins assigned on LQFP-48 ({len(LQFP48_PINS)} GPIO-capable pins), unassigned: {spare or 'none'}")
    for w in warnings:
        print("WARN ", w)
    for e in errors:
        print("ERROR", e)
    if errors:
        print(f"\n{len(errors)} conflict(s) found")
        return 1
    print("\nOK: no pin conflicts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
