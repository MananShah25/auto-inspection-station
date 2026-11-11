# I/O Map

This project uses OpenPLC IEC addresses with Modbus TCP access. In the default OpenPLC mapping, `%IX` bits are discrete inputs, `%QX` bits are coils, `%IW` words are input registers, and `%QW` words are holding registers. Modbus clients should use zero-based addresses unless a specific client tool documents a one-based display convention.

Reference: [OpenPLC/Autonomy Edge Modbus addressing](https://edge.autonomylogic.com/docs/openplc-editor/communication/modbus/addressing/).

## Design Rules

- This file is the source of truth for every external Modbus address.
- Harness scenarios must refer to signal names from `harness.modbus_client`, not numeric addresses.
- Safety-critical outputs are commanded by PLC logic only; the harness stimulates inputs and reads outputs/state.
- Normally-closed safety inputs are healthy when `TRUE` and unsafe when `FALSE`.
- All timings are measured in milliseconds unless stated otherwise.
- Real field input names use `%IX`/`%IW`. Because those Modbus areas are commonly read-only to an external client, the automated harness drives the writable simulation input layer under `SIM_*` signals. Ladder logic maps either field inputs or simulation inputs into internal canonical `IN_*` tags.

## Discrete Inputs (`%IX`, Modbus Function 2)

| Signal | IEC Address | Modbus Address | Type | Normal/Active Meaning | Description |
|---|---:|---:|---|---|---|
| `UNIT_AT_INSPECTION` | `%IX0.0` | 0 | BOOL | `TRUE` = unit present | Photoeye at the inspection station. Rising edge starts a unit cycle. |
| `UNIT_AT_REJECT` | `%IX0.1` | 1 | BOOL | `TRUE` = unit at reject point | Photoeye confirming a failed unit has reached the reject pusher. |
| `VISION_PASS` | `%IX0.2` | 2 | BOOL | `TRUE` = pass, `FALSE` = fail | Pass/fail result from the simulated inspection system. Valid only when `VISION_RESULT_VALID` is true. |
| `VISION_RESULT_VALID` | `%IX0.3` | 3 | BOOL | `TRUE` = result available | Indicates the vision result is ready to be latched after the stability timer. |
| `ESTOP_OK_NC` | `%IX0.4` | 4 | BOOL | `TRUE` = E-stop circuit healthy | Normally-closed E-stop input. `FALSE` means pressed, wiring fault, or unsafe. |
| `GUARD_CLOSED_NC` | `%IX0.5` | 5 | BOOL | `TRUE` = guard closed | Normally-closed guard-door interlock. `FALSE` blocks pusher extension. |
| `AUTO_MODE` | `%IX0.6` | 6 | BOOL | `TRUE` = automatic mode selected | Enables automatic station sequence when safety inputs are healthy. |
| `CYCLE_START` | `%IX0.7` | 7 | BOOL | `TRUE` = start requested | Operator start command used to enter `READY` from `IDLE`. |
| `RESET_PB` | `%IX1.0` | 8 | BOOL | `TRUE` = reset pressed | Momentary reset pushbutton. PLC logic must use rising-edge behavior. |
| `PUSHER_EXTENDED` | `%IX1.1` | 9 | BOOL | `TRUE` = extend confirmed | End-of-stroke confirmation for pusher extension. |
| `PUSHER_RETRACTED` | `%IX1.2` | 10 | BOOL | `TRUE` = retract confirmed | Home-position confirmation for pusher retraction. |
| `DOWNSTREAM_CLEAR` | `%IX1.3` | 11 | BOOL | `TRUE` = safe to release | Simulated downstream permissive for pass release. |

## Coils / Discrete Outputs (`%QX`, Modbus Function 1)

| Signal | IEC Address | Modbus Address | Type | Energized Meaning | Description |
|---|---:|---:|---|---|---|
| `CONVEYOR_RUN` | `%QX0.0` | 0 | BOOL | Conveyor motor commanded on | Runs only during `READY` and `PASS_RELEASE` while safety is healthy. |
| `PUSHER_EXTEND` | `%QX0.1` | 1 | BOOL | Pusher solenoid extend energized | Extends reject pusher. Hard interlocked against `PUSHER_RETRACT`. |
| `PUSHER_RETRACT` | `%QX0.2` | 2 | BOOL | Pusher solenoid retract energized | Retracts reject pusher. Hard interlocked against `PUSHER_EXTEND`. |
| `PASS_LAMP` | `%QX0.3` | 3 | BOOL | Last/completing unit passed | Operator pass indication. |
| `FAIL_LAMP` | `%QX0.4` | 4 | BOOL | Last/completing unit failed | Operator fail/reject indication. |
| `FAULT_LAMP` | `%QX0.5` | 5 | BOOL | Fault active | Indicates latched station fault. |
| `STATION_READY` | `%QX0.6` | 6 | BOOL | Ready for a unit | Indicates automatic mode, safety healthy, no fault, and state `READY`. |

## Simulation Input Coils (`%QX`, Modbus Function 1)

These writable coils allow the Python harness to drive the PLC over Modbus TCP. They are not physical outputs despite living in the coil address space; they are test/simulation inputs consumed by ladder logic when `SIM_MODE` is enabled.

| Signal | IEC Address | Modbus Address | Type | Normal/Active Meaning | Description |
|---|---:|---:|---|---|---|
| `SIM_MODE` | `%QX2.0` | 16 | BOOL | `TRUE` = use simulation inputs | Selects `SIM_*` coils/registers instead of physical `%IX`/`%IW` inputs. |
| `SIM_UNIT_AT_INSPECTION` | `%QX2.1` | 17 | BOOL | `TRUE` = unit present | Harness-driven equivalent of `UNIT_AT_INSPECTION`. |
| `SIM_UNIT_AT_REJECT` | `%QX2.2` | 18 | BOOL | `TRUE` = unit at reject point | Harness-driven equivalent of `UNIT_AT_REJECT`. |
| `SIM_VISION_PASS` | `%QX2.3` | 19 | BOOL | `TRUE` = pass, `FALSE` = fail | Harness-driven equivalent of `VISION_PASS`. |
| `SIM_VISION_RESULT_VALID` | `%QX2.4` | 20 | BOOL | `TRUE` = result available | Harness-driven equivalent of `VISION_RESULT_VALID`. |
| `SIM_ESTOP_OK_NC` | `%QX2.5` | 21 | BOOL | `TRUE` = E-stop circuit healthy | Harness-driven equivalent of `ESTOP_OK_NC`. Defaults should be safe/false until initialized. |
| `SIM_GUARD_CLOSED_NC` | `%QX2.6` | 22 | BOOL | `TRUE` = guard closed | Harness-driven equivalent of `GUARD_CLOSED_NC`. |
| `SIM_AUTO_MODE` | `%QX2.7` | 23 | BOOL | `TRUE` = automatic mode selected | Harness-driven equivalent of `AUTO_MODE`. |
| `SIM_CYCLE_START` | `%QX3.0` | 24 | BOOL | `TRUE` = start requested | Harness-driven equivalent of `CYCLE_START`. |
| `SIM_RESET_PB` | `%QX3.1` | 25 | BOOL | `TRUE` = reset pressed | Harness-driven equivalent of `RESET_PB`. |
| `SIM_PUSHER_EXTENDED` | `%QX3.2` | 26 | BOOL | `TRUE` = extend confirmed | Harness-driven equivalent of `PUSHER_EXTENDED`. |
| `SIM_PUSHER_RETRACTED` | `%QX3.3` | 27 | BOOL | `TRUE` = retract confirmed | Harness-driven equivalent of `PUSHER_RETRACTED`. |
| `SIM_DOWNSTREAM_CLEAR` | `%QX3.4` | 28 | BOOL | `TRUE` = safe to release | Harness-driven equivalent of `DOWNSTREAM_CLEAR`. |

## Input Registers (`%IW`, Modbus Function 4)

These are the physical/field-side register names. Automated tests should use the writable simulation holding registers below unless the selected OpenPLC setup explicitly supports writing input registers.

| Signal | IEC Address | Modbus Address | Type | Units / Encoding | Description |
|---|---:|---:|---|---|---|
| `UNIT_SERIAL_IN` | `%IW0` | 0 | UINT | Integer serial | Serial number for the unit at inspection. |
| `FAIL_REASON_IN` | `%IW1` | 1 | UINT | `0` none, `1` vision defect, `2` dimension, `3` barcode, `4` timeout/test | Failure reason supplied by the simulated inspection system. |

## Holding Registers / PLC Status (`%QW`, Modbus Function 3)

| Signal | IEC Address | Modbus Address | Type | Units / Encoding | Description |
|---|---:|---:|---|---|---|
| `STATE_CODE` | `%QW0` | 0 | UINT | See state code table | Current PLC state for harness assertions and diagnostics. |
| `TOTAL_UNITS` | `%QW1` | 1 | UINT | Count | Total completed units since reset/power-up. |
| `TOTAL_REJECTS` | `%QW2` | 2 | UINT | Count | Total rejected units since reset/power-up. |
| `LAST_CYCLE_TIME_MS` | `%QW3` | 3 | UINT | ms | Most recent completed unit cycle time. |
| `FAULT_CODE` | `%QW4` | 4 | UINT | See fault code table | Latched fault reason. |
| `LAST_SERIAL` | `%QW5` | 5 | UINT | Integer serial | Serial number for the most recently completed unit. |
| `LAST_RESULT` | `%QW6` | 6 | UINT | `1` pass, `2` fail | Result for the most recently completed unit. |
| `LAST_FAIL_REASON` | `%QW7` | 7 | UINT | Same as `FAIL_REASON_IN` | Failure reason for the most recently completed failed unit; `0` for pass. |
| `SCENARIO_STEP` | `%QW8` | 8 | UINT | Test-controlled marker | Optional diagnostic marker written by harness only if enabled in simulator mode. |

## Simulation Input Holding Registers (`%QW`, Modbus Function 3/6/16)

These writable holding registers provide test-mode equivalents for field input registers.

| Signal | IEC Address | Modbus Address | Type | Units / Encoding | Description |
|---|---:|---:|---|---|---|
| `SIM_UNIT_SERIAL_IN` | `%QW20` | 20 | UINT | Integer serial | Harness-driven equivalent of `UNIT_SERIAL_IN`. |
| `SIM_FAIL_REASON_IN` | `%QW21` | 21 | UINT | Same as `FAIL_REASON_IN` | Harness-driven equivalent of `FAIL_REASON_IN`. |

## Internal Canonical Inputs

Ladder logic should use these internal names after the input-mapping rungs. In physical mode they mirror `%IX`/`%IW`; in simulation mode they mirror `SIM_*` coils/registers.

| Canonical Tag | Physical Source | Simulation Source |
|---|---|---|
| `IN_UNIT_AT_INSPECTION` | `UNIT_AT_INSPECTION` | `SIM_UNIT_AT_INSPECTION` |
| `IN_UNIT_AT_REJECT` | `UNIT_AT_REJECT` | `SIM_UNIT_AT_REJECT` |
| `IN_VISION_PASS` | `VISION_PASS` | `SIM_VISION_PASS` |
| `IN_VISION_RESULT_VALID` | `VISION_RESULT_VALID` | `SIM_VISION_RESULT_VALID` |
| `IN_ESTOP_OK_NC` | `ESTOP_OK_NC` | `SIM_ESTOP_OK_NC` |
| `IN_GUARD_CLOSED_NC` | `GUARD_CLOSED_NC` | `SIM_GUARD_CLOSED_NC` |
| `IN_AUTO_MODE` | `AUTO_MODE` | `SIM_AUTO_MODE` |
| `IN_CYCLE_START` | `CYCLE_START` | `SIM_CYCLE_START` |
| `IN_RESET_PB` | `RESET_PB` | `SIM_RESET_PB` |
| `IN_PUSHER_EXTENDED` | `PUSHER_EXTENDED` | `SIM_PUSHER_EXTENDED` |
| `IN_PUSHER_RETRACTED` | `PUSHER_RETRACTED` | `SIM_PUSHER_RETRACTED` |
| `IN_DOWNSTREAM_CLEAR` | `DOWNSTREAM_CLEAR` | `SIM_DOWNSTREAM_CLEAR` |
| `IN_UNIT_SERIAL` | `UNIT_SERIAL_IN` | `SIM_UNIT_SERIAL_IN` |
| `IN_FAIL_REASON` | `FAIL_REASON_IN` | `SIM_FAIL_REASON_IN` |

## State Codes

| Code | State |
|---:|---|
| 0 | `IDLE` |
| 10 | `READY` |
| 20 | `INSPECTING` |
| 30 | `PASS_RELEASE` |
| 40 | `REJECT_EXTEND` |
| 50 | `REJECT_RETRACT` |
| 90 | `FAULT` |

## Fault Codes

| Code | Fault |
|---:|---|
| 0 | No fault |
| 100 | E-stop circuit open or E-stop pressed |
| 110 | Guard door open during pusher demand |
| 120 | Pusher extend timeout |
| 130 | Pusher retract timeout |
| 140 | Unit-present sensor stuck high |
| 150 | Vision result unstable |
| 160 | Unsafe pusher command conflict detected |

## Timing Constants

| Constant | Value | Purpose |
|---|---:|---|
| `VISION_STABLE_MS` | 250 ms | Vision result must remain valid and unchanged before latch. |
| `PASS_RELEASE_MS` | 500 ms | Conveyor release window for a passing unit. |
| `PUSHER_EXTEND_TIMEOUT_MS` | 1500 ms | Maximum allowed wait for `PUSHER_EXTENDED`. |
| `PUSHER_RETRACT_TIMEOUT_MS` | 1500 ms | Maximum allowed wait for `PUSHER_RETRACTED`. |
| `REJECT_SETTLE_MS` | 250 ms | Short dwell after extension confirmation before retracting. |
| `UNIT_STUCK_HIGH_MS` | 3000 ms | Fault if inspection sensor remains high too long after cycle completion. |
