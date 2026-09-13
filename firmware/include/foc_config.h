/**
 * foc_config.h — board-level constants for the CAN-BUS FOC actuator.
 *
 * Every value here is derived in hardware/calc/design_calcs.py and documented in
 * docs/04-firmware-capability.md §5.  Change the hardware -> change the script
 * -> change this file.  Nothing in the control code hard-codes these.
 */
#ifndef FOC_CONFIG_H
#define FOC_CONFIG_H

/* ---- Clocks ------------------------------------------------------------ */
#define SYSCLK_HZ                 170000000UL   /* 8 MHz HSE, PLLM=2 PLLN=85 PLLR=2 */
#define HSE_HZ                    8000000UL

/* ---- PWM / TIM1 -------------------------------------------------------- */
#define PWM_FREQ_HZ               20000U
#define TIM1_ARR                  (SYSCLK_HZ / (2U * PWM_FREQ_HZ))   /* 4250, centre-aligned */
#define DEAD_TIME_NS              400U
#define TIM1_DTG                  ((DEAD_TIME_NS * (SYSCLK_HZ / 1000000UL)) / 1000U) /* 68 */
#define PWM_MAX_DUTY              0.96f       /* leave bootstrap refresh time */

/* ---- Loop rates -------------------------------------------------------- */
#define CURRENT_LOOP_HZ           PWM_FREQ_HZ
#define VELOCITY_LOOP_DIV         5U          /* 4 kHz  */
#define POSITION_LOOP_DIV         20U         /* 1 kHz  */

/* ---- Current sense: INA240A1 (20 V/V) + 2 x ERJ8CWFR030V parallel ------- */
#define SHUNT_OHM                 0.015f
#define CSA_GAIN                  20.0f
#define ISENSE_V_PER_A            (SHUNT_OHM * CSA_GAIN)    /* 0.30 V/A */
#define ISENSE_OFFSET_V_NOMINAL   1.65f                     /* REF = VS/2, auto-cal at boot */
#define I_MAX_A                   5.0f                      /* amplifier swing limit */
#define I_TRIP_A                  5.5f                      /* software trip */
#define I_CONT_A_RMS              3.5f                      /* thermal / connector */
#define CURRENT_SENSE_PHASES      2                         /* 3 if the PA7 INA240 is populated */

/* ---- ADC --------------------------------------------------------------- */
#define ADC_VREF_V                3.3f
#define ADC_BITS                  12U
#define ADC_V_PER_LSB             (ADC_VREF_V / (float)(1U << ADC_BITS))
#define VBUS_DIV_TOP_OHM          20000.0f   /* 2 x 10k series */
#define VBUS_DIV_BOT_OHM          2200.0f
#define VBUS_V_PER_LSB            (ADC_V_PER_LSB * (VBUS_DIV_TOP_OHM + VBUS_DIV_BOT_OHM) / VBUS_DIV_BOT_OHM)
#define NTC_R25_OHM               10000.0f
#define NTC_BETA                  3950.0f
#define NTC_PULLUP_OHM            10000.0f

/* ---- Bus limits (AO3400A 30 V) ----------------------------------------- */
#define VBUS_MIN_V                10.0f
#define VBUS_MAX_V                20.0f      /* raise to 28 V only with >= 40 V FETs */
#define VBUS_NOMINAL_V            16.0f

/* ---- Encoder ----------------------------------------------------------- */
#define ENCODER_BITS              14U        /* MT6701 */
#define ENCODER_CPR               (1U << ENCODER_BITS)
#define ENCODER_SPI_HZ            1000000UL

/* ---- CAN --------------------------------------------------------------- */
#define CAN_BITRATE               1000000UL  /* SN65HVD230 limit */
#define CAN_HEARTBEAT_TIMEOUT_MS  100U
#define CAN_FEEDBACK_HZ           1000U
#define CAN_STATUS_HZ             10U

/* ---- Pins (documented in docs/03-pin-assignment.md) -------------------- */
#define PIN_PWM_AH   GPIOA, 8    /* TIM1_CH1  AF6 */
#define PIN_PWM_BH   GPIOA, 9    /* TIM1_CH2  AF6 */
#define PIN_PWM_CH   GPIOA, 10   /* TIM1_CH3  AF6 */
#define PIN_PWM_AL   GPIOB, 13   /* TIM1_CH1N AF6 */
#define PIN_PWM_BL   GPIOB, 14   /* TIM1_CH2N AF6 */
#define PIN_PWM_CL   GPIOB, 15   /* TIM1_CH3N AF4 (!) */
#define PIN_DRV_FLT  GPIOB, 12   /* TIM1_BKIN AF6, active low */
#define PIN_DRV_EN   GPIOB, 2
#define PIN_ISENSE_A GPIOA, 0    /* ADC1_IN1 */
#define PIN_ISENSE_B GPIOA, 1    /* ADC2_IN2 */
#define PIN_ISENSE_C GPIOA, 7    /* ADC2_IN4, optional */
#define PIN_VBUS     GPIOA, 2    /* ADC1_IN3 */
#define PIN_NTC      GPIOA, 3    /* ADC1_IN4 */
#define PIN_ENC_CS   GPIOA, 4
#define PIN_ENC_SCK  GPIOA, 5    /* SPI1 AF5 */
#define PIN_ENC_MISO GPIOA, 6    /* SPI1 AF5 */
#define PIN_CAN_RX   GPIOA, 11   /* FDCAN1 AF9 */
#define PIN_CAN_TX   GPIOA, 12   /* FDCAN1 AF9 */
#define PIN_UART_TX  GPIOB, 3    /* USART2 AF7 */
#define PIN_UART_RX  GPIOB, 4    /* USART2 AF7 */
#define PIN_I2C_SCL  GPIOB, 6    /* I2C1 AF4 */
#define PIN_I2C_SDA  GPIOB, 7    /* I2C1 AF4 */
#define PIN_LED      GPIOB, 9
#define PIN_ID0      GPIOC, 13
#define PIN_ID1      GPIOC, 14
#define PIN_ID2      GPIOC, 15

#endif /* FOC_CONFIG_H */
