# Station State Machine

The PLC program controls a simulated inspection and reject station. A unit arrives at the inspection point, the station latches a stable inspection result, then either releases the unit downstream or rejects it with a pusher. Safety faults can interrupt the sequence from any state.

The state machine consumes canonical internal inputs named `IN_*`. In physical mode these mirror the `%IX`/`%IW` field inputs. In simulation mode they mirror Modbus-writable `SIM_*` coils and holding registers so the automated Python harness can drive scenarios through the same PLC state machine.

## State Summary

| Code | State | Conveyor | Pusher Extend | Pusher Retract | Meaning |
|---:|---|---|---|---|---|
| 0 | `IDLE` | Off | Off | Off | Station is not in automatic operation. |
| 10 | `READY` | On | Off | Off | Station is healthy and waiting for a unit. |
| 20 | `INSPECTING` | Off | Off | Off | Unit is stopped and inspection result is being stabilized. |
| 30 | `PASS_RELEASE` | On | Off | Off | Passed unit is being released downstream. |
| 40 | `REJECT_EXTEND` | Off | On when permitted | Off | Failed unit is being pushed into reject bin. |
| 50 | `REJECT_RETRACT` | Off | Off | On | Pusher is returning home. |
| 90 | `FAULT` | Off | Off | Off | Latched unsafe or abnormal condition. |

## Global Safety Rules

- If `IN_ESTOP_OK_NC` is `FALSE`, all outputs drop immediately, `FAULT` latches, and `FAULT_CODE` becomes `100`.
- `IN_RESET_PB` is rising-edge triggered. Holding reset high must not repeatedly clear faults.
- Reset only clears a fault when `IN_ESTOP_OK_NC`, `IN_GUARD_CLOSED_NC`, `IN_AUTO_MODE`, and `IN_PUSHER_RETRACTED` are all true.
- `PUSHER_EXTEND` and `PUSHER_RETRACT` must never energize together. A hard output interlock suppresses both if a conflict is detected and latches fault `160`.
- If `IN_GUARD_CLOSED_NC` becomes `FALSE` while pusher extension is demanded, extension drops and fault `110` latches.
- Fault state requires explicit reset; restoring the unsafe input alone never auto-clears `FAULT`.

## Transition Table

| From | Condition | To | Actions |
|---|---|---|---|
| Power-up | First scan | `IDLE` | Clear output commands. Initialize state/status registers. |
| `IDLE` | `IN_AUTO_MODE` and `IN_CYCLE_START` and all safety permissives healthy | `READY` | Turn on `STATION_READY`; allow conveyor run. |
| `READY` | `IN_AUTO_MODE` false | `IDLE` | Stop conveyor; clear ready output. |
| `READY` | Rising edge of `IN_UNIT_AT_INSPECTION` | `INSPECTING` | Stop conveyor; capture `IN_UNIT_SERIAL`; start cycle timer; start vision stability monitoring. |
| `INSPECTING` | `IN_VISION_RESULT_VALID` true and `IN_VISION_PASS` stable for `VISION_STABLE_MS` | `PASS_RELEASE` | Latch result `PASS`; set `PASS_LAMP`; clear fail reason. |
| `INSPECTING` | `IN_VISION_RESULT_VALID` true and fail result stable for `VISION_STABLE_MS` | `REJECT_EXTEND` | Latch result `FAIL`; capture `IN_FAIL_REASON`; set `FAIL_LAMP`. |
| `INSPECTING` | Result changes while stability timer is active | `INSPECTING` or `FAULT` | Restart stability timer once; if instability exceeds allowed window, fault `150`. |
| `PASS_RELEASE` | `PASS_RELEASE_MS` elapsed and `IN_DOWNSTREAM_CLEAR` true | `READY` | Increment `TOTAL_UNITS`; calculate `LAST_CYCLE_TIME_MS`; publish last-result registers. |
| `PASS_RELEASE` | `IN_UNIT_AT_INSPECTION` remains true longer than `UNIT_STUCK_HIGH_MS` after release | `FAULT` | Latch fault `140`. |
| `REJECT_EXTEND` | `IN_GUARD_CLOSED_NC` false | `FAULT` | Drop pusher output; latch fault `110`. |
| `REJECT_EXTEND` | `IN_PUSHER_EXTENDED` true before timeout | `REJECT_RETRACT` | Stop extend output after `REJECT_SETTLE_MS`; command retract. |
| `REJECT_EXTEND` | `PUSHER_EXTEND_TIMEOUT_MS` elapsed without `IN_PUSHER_EXTENDED` | `FAULT` | Drop pusher output; latch fault `120`. |
| `REJECT_RETRACT` | `IN_PUSHER_RETRACTED` true before timeout | `READY` | Increment `TOTAL_UNITS` and `TOTAL_REJECTS`; calculate `LAST_CYCLE_TIME_MS`; publish last-result registers. |
| `REJECT_RETRACT` | `PUSHER_RETRACT_TIMEOUT_MS` elapsed without `IN_PUSHER_RETRACTED` | `FAULT` | Drop pusher output; latch fault `130`. |
| Any non-fault state | `IN_ESTOP_OK_NC` false | `FAULT` | Drop all outputs; latch fault `100`. |
| Any state with pusher demand | Extend and retract demand both true | `FAULT` | Suppress both solenoids; latch fault `160`. |
| `FAULT` | Reset rising edge and all reset permissives healthy | `IDLE` | Clear fault latch and fault code; outputs remain off until start sequence. |

## Output Rules

| Output | Energized When |
|---|---|
| `CONVEYOR_RUN` | State is `READY`, or state is `PASS_RELEASE` and `IN_DOWNSTREAM_CLEAR` is true. |
| `PUSHER_EXTEND` | State is `REJECT_EXTEND`, guard is closed, E-stop circuit is healthy, and retract output is not commanded. |
| `PUSHER_RETRACT` | State is `REJECT_RETRACT`, E-stop circuit is healthy, and extend output is not commanded. |
| `PASS_LAMP` | Last latched result is pass and no active fault. |
| `FAIL_LAMP` | Last latched result is fail and no active fault. |
| `FAULT_LAMP` | Fault latch is active. |
| `STATION_READY` | State is `READY`, no fault is active, auto mode is on, E-stop is healthy, and guard is closed. |

## Traceability Events

A traceability record is eligible to be written exactly once when a unit reaches a completed state transition:

- Pass record: `PASS_RELEASE -> READY`
- Fail record: `REJECT_RETRACT -> READY`

The PLC exposes `LAST_SERIAL`, `LAST_RESULT`, `LAST_FAIL_REASON`, `LAST_CYCLE_TIME_MS`, `TOTAL_UNITS`, and `TOTAL_REJECTS`. The Python traceability logger records the row in SQLite after observing a new completed unit count.

## Open Questions To Validate During Runtime Integration

- Whether the selected OpenPLC runtime exposes `%IW` as writable from the harness or requires simulator-side mirroring through holding registers.
- Whether the OpenPLC scan interval produces stable observed timing with the proposed millisecond thresholds.
- Whether the graphical ladder editor exports enough ST/XML detail to commit meaningfully, or whether the rung specification remains the primary review artifact.
