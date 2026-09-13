# 03 — STM32G431CBT6 pin assignment & conflict analysis

Machine-checked: `python3 tools/check_pinmap.py` validates
`hardware/pinmap/pinmap.csv` against the LQFP-48 bonding list and the
alternate-function table (DS12589 / RM0440) and exits non-zero on any
conflict. **Current result: 38/38 GPIO-capable pins assigned, 0 conflicts.**

## 1. The map

| Pin | Signal | Peripheral | AF | Why this pin |
|---|---|---|---|---|
| PA8 | PWM_AH | TIM1_CH1 | 6 | Only TIM1_CH1-3 location on LQFP-48 (PC0-2 are not bonded). |
| PA9 | PWM_BH | TIM1_CH2 | 6 | |
| PA10 | PWM_CH | TIM1_CH3 | 6 | |
| PB13 | PWM_AL | TIM1_CH1N | 6 | PB13-15 chosen over PA7/PB0/PB1 so those stay free as ADC inputs. |
| PB14 | PWM_BL | TIM1_CH2N | 6 | |
| PB15 | PWM_CL | TIM1_CH3N | **4** | Note: AF4 on this pin, not AF6. |
| PB12 | DRV_nFAULT | TIM1_BKIN | 6 | Hardware break. PB8 (AF12) was rejected — it is BOOT0. |
| PB2 | DRV_EN | GPIO out | — | Ordinary pin; external 10 k pull-down keeps the bridge off through reset. |
| PA0 | ISENSE_A | ADC1_IN1 | — | ADC1 injected rank 1. |
| PA1 | ISENSE_B | ADC2_IN2 | — | ADC2 injected rank 1 → dual-simultaneous with PA0 on the TIM1 trigger. |
| PA7 | ISENSE_C (opt) | ADC2_IN4 | — | Reserved for 3-shunt. Doubles as SPI1_MOSI if a 4-wire SPI encoder is ever needed. |
| PA2 | VBUS_SENSE | ADC1_IN3 | — | Regular group, DMA. |
| PA3 | TEMP_NTC | ADC1_IN4 | — | Regular group, DMA. |
| PA4 | ENC_CS | GPIO out | — | |
| PA5 | ENC_SCK | SPI1_SCK | 5 | |
| PA6 | ENC_MISO | SPI1_MISO | 5 | Receive-only SSI; MOSI not needed. |
| PA11 | CAN_RX | FDCAN1_RX | 9 | Chosen over PB8 (BOOT0 — a CAN RX idles high and would enter the ROM bootloader). |
| PA12 | CAN_TX | FDCAN1_TX | 9 | |
| PA13 | SWDIO | SYS | 0 | |
| PA14 | SWCLK | SYS | 0 | |
| PB3 | UART_TX | USART2_TX | 7 | Sacrifices SWO; SWD 2-wire is enough. PA2/PA3 (the other USART2 site) are the ADC inputs. |
| PB4 | UART_RX | USART2_RX | 7 | |
| PB6 | I2C_SCL | I2C1_SCL | 4 | Alternate encoder (AS5600). PB8/PB9 rejected — BOOT0 again. |
| PB7 | I2C_SDA | I2C1_SDA | 4 | |
| PB8 | BOOT0 | — | — | 10 k pull-down + test point. **Nothing else.** |
| PB9 | STATUS_LED | GPIO out | — | |
| PC13 | NODE_ID0 | GPIO in | — | 0 Ω strap. |
| PC14 | NODE_ID1 | GPIO in | — | OSC32 unused (no LSE). |
| PC15 | NODE_ID2 | GPIO in | — | |
| PF0 | OSC_IN | HSE | — | 8 MHz + 30 pF. |
| PF1 | OSC_OUT | HSE | — | |
| PG10 | NRST | — | — | |
| PA15, PB0, PB1, PB5, PB10, PB11 | spare | | | PB0/PB1 are ADC1_IN15/IN12 (2nd NTC or 3rd shunt on ADC1). PB5/PB10/PB11 are the hall/ABZ alternate for J3. |

## 2. Conflicts found and resolved during assignment

These are the real traps on this package; each is a hard error in the checker.

| Trap | Effect if ignored | Resolution |
|---|---|---|
| **PB8 = BOOT0 on LQFP-48.** FDCAN1_RX (AF9), I2C1_SCL (AF4) and TIM1_BKIN (AF12) all live there and all idle **high**. | MCU samples BOOT0 = 1 at reset → boots into the ROM bootloader, firmware never runs (intermittently, depending on whether the bus/cable is connected). | CAN on PA11/PA12, I2C on PB6/PB7, BKIN on PB12. PB8 is BOOT0 only, with a pull-down. |
| TIM1_CH1N-3N have two full sets: PA7/PB0/PB1 (AF6) and PB13/PB14/PB15 (AF6/6/4). | Using the PA7/PB0/PB1 set eats three of the best ADC pins (ADC2_IN4, ADC1_IN15, ADC1_IN12). | Use PB13/14/15. |
| PB15 TIM1_CH3N is **AF4**, the other five TIM1 pins are AF6. | Wrong AF = phase C low-side never switches; motor "works" on two phases and cooks. | Documented; checker enforces the per-pin AF number. |
| USART2 default site PA2/PA3 collides with the analog inputs. | | USART2 on PB3/PB4 (AF7). PB3/PB4 are JTAG pins at reset — firmware selects SWD-only, then they are free. |
| USART1 default PA9/PA10 collides with TIM1_CH2/CH3. | | Not used. |
| Dual-simultaneous ADC needs one shunt on ADC1 and one on ADC2 with no shared channel. | Sequential sampling adds ~1 µs skew between Ia and Ib → torque ripple. | PA0 → ADC1_IN1, PA1 → ADC2_IN2 (checker asserts this). |
| PC13 is a low-drive pin (3 mA) in the RTC domain. | Unreliable as an output. | Used as an input (ID strap) only. |
| PF0 is also ADC1_IN10 and TIM1_CH3N (AF6). | | Irrelevant — it is the crystal. |

## 3. Peripheral budget

| Peripheral | Used for | Free instances |
|---|---|---|
| TIM1 | 6-ch complementary PWM, dead time, break, ADC trigger (TRGO2) | TIM2/3/4/8/15/16/17 for hall/encoder timing, control-loop tick |
| ADC1 + ADC2 | injected: Ia/Ib simultaneous; regular: VBUS, NTC, Vrefint, Tsense via DMA | — (G431 has 2 ADCs) |
| FDCAN1 | bus | — |
| SPI1 | encoder SSI | SPI2/3 |
| I2C1 | alt encoder | I2C2/3 |
| USART2 | debug / SimpleFOC commander | USART1/3, LPUART1 |
| CORDIC | sin/cos, atan2 | — |
| FMAC | optional IIR on velocity | — |
| OPAMP1-3 | unused (could replace INA240 for a low-side 3rd shunt: OPAMP1 on PA1/PA3 → not free; OPAMP2 on PA7/PA5 — conflicts with SPI; leave unused) | |
| COMP1-4 | optional: VBUS over-voltage → TIM1_BKIN2 for a second hardware trip | |
| DAC1 | unused (PA4/PA5 taken) | |

## 4. Firmware-side pin config summary (for the HAL / CubeMX)

```
TIM1   : CH1/CH2/CH3 + CH1N/CH2N/CH3N, center-aligned mode 1, ARR=4250 (20 kHz),
         DTG=68 (400 ns), BKIN active-low on PB12, TRGO2 = OC4REF (ADC trigger at counter top)
ADC1   : injected IN1 (PA0) ext-trig TIM1_TRGO2; regular IN3, IN4, IN16(temp), IN18(Vrefint) DMA circular
ADC2   : injected IN2 (PA1), dual mode = regular+injected simultaneous, slave of ADC1
FDCAN1 : PA11/PA12 AF9, classic CAN, 1 Mbps (8 MHz HSE → PLL → 170 MHz; FDCAN clk = PCLK1 170 MHz,
         prescaler 10 → 17 MHz, TSEG1 13, TSEG2 3, SJW 3 → 1.000 Mbps, sample point 82 %)
SPI1   : PA5/PA6 AF5, master, 8-bit, CPOL=1 CPHA=1 for MT6701 SSI, ~1 MHz; PA4 GPIO CS
I2C1   : PB6/PB7 AF4, 400 kHz, only if I2C encoder populated
USART2 : PB3/PB4 AF7, 115200 8N1 (JTAG disabled → SWD only)
GPIO   : PB2 out (DRV_EN, init low), PB9 out (LED), PC13/14/15 in pull-down (ID)
RCC    : HSE 8 MHz bypass=off, PLLM=2 PLLN=85 PLLR=2 → 170 MHz; HSE drive = high (20 pF crystal)
```
