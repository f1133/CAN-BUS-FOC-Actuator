# 05 — CAN protocol (classic CAN, 1 Mbps, 11-bit IDs)

Bus budget from `design_calcs.py` §8: three joints with one 4-byte command and
one 8-byte feedback per 1 ms cycle:

`3 × (95 + 133) µs = 684 µs → 68 % load`. Acceptable ceiling. If a fourth joint
is added, drop feedback to 500 Hz or move to a 5 Mbps FD transceiver.

## ID layout

`ID = (CMD << 4) | NODE_ID`, NODE_ID 0–7 from the PC13-15 straps (0 = broadcast
receiver only, host uses 0xF).

| CMD | Dir | Payload | Rate |
|---|---|---|---|
| 0x1 SET_TORQUE | host → joint | int16 τ* (mNm), int16 reserved | 1 kHz |
| 0x2 SET_IMPEDANCE | host → joint | int16 θ* (1/100 °), int16 ω* (1/10 °/s), uint8 Kp, uint8 Kd, int16 τff — 8 bytes (MIT mini-cheetah style) | 1 kHz |
| 0x3 SET_MODE | host → joint | uint8 {IDLE, TORQUE, VELOCITY, POSITION, IMPEDANCE, CALIBRATE, BRAKE} | on change |
| 0x4 SET_LIMITS | host → joint | int16 I_max (mA), int16 ω_max, int16 θ_min, int16 θ_max | on change |
| 0x5 FEEDBACK | joint → host | int16 θ (1/100 °), int16 ω (1/10 °/s), int16 Iq (mA), uint8 T (°C), uint8 status | 1 kHz |
| 0x6 STATUS | joint → host | uint16 fault bits, uint16 VBUS (mV), uint8 mode, uint8 fw_ver | 10 Hz |
| 0x7 HEARTBEAT | host → all (NODE 0) | uint8 counter | 100 Hz; timeout 100 ms → BRAKE |
| 0x8 PARAM_RW | both | uint8 index, uint8 rw, float32 value | on demand |
| 0xE BOOTLOADER | host → joint | — | enters CAN bootloader |

Status bits: OVERCURRENT, OVERVOLT, UNDERVOLT, OVERTEMP, ENCODER_ERR,
DRIVER_FAULT (nFAULT), HEARTBEAT_LOST, CALIBRATED.
