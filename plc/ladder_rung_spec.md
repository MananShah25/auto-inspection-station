# Ladder Rung Specification

This document is the exact ladder-logic design to transcribe into OpenPLC Editor. Sequential control and safety interlocks are specified as ladder rungs. Structured Text is reserved for status-register arithmetic and compact code assignment as noted in the ST sections.

## Addressed Signals

Use the external signals from `plc/io_map.md` exactly as named.

## Internal Bits

| Internal Tag | Type | Purpose |
|---|---|---|
| `S_IDLE` | BOOL | One-hot state bit for `IDLE`. |
| `S_READY` | BOOL | One-hot state bit for `READY`. |
| `S_INSPECTING` | BOOL | One-hot state bit for `INSPECTING`. |
| `S_PASS_RELEASE` | BOOL | One-hot state bit for `PASS_RELEASE`. |
| `S_REJECT_EXTEND` | BOOL | One-hot state bit for `REJECT_EXTEND`. |
| `S_REJECT_RETRACT` | BOOL | One-hot state bit for `REJECT_RETRACT`. |
| `S_FAULT` | BOOL | One-hot state bit for `FAULT`. |
| `IN_UNIT_AT_INSPECTION` | BOOL | Canonical unit-present input after physical/simulation mapping. |
| `IN_UNIT_AT_REJECT` | BOOL | Canonical reject-point input after physical/simulation mapping. |
| `IN_VISION_PASS` | BOOL | Canonical vision pass/fail input after physical/simulation mapping. |
| `IN_VISION_RESULT_VALID` | BOOL | Canonical vision-valid input after physical/simulation mapping. |
| `IN_ESTOP_OK_NC` | BOOL | Canonical E-stop healthy-high input after physical/simulation mapping. |
| `IN_GUARD_CLOSED_NC` | BOOL | Canonical guard healthy-high input after physical/simulation mapping. |
| `IN_AUTO_MODE` | BOOL | Canonical auto-mode input after physical/simulation mapping. |
| `IN_CYCLE_START` | BOOL | Canonical start input after physical/simulation mapping. |
| `IN_RESET_PB` | BOOL | Canonical reset input after physical/simulation mapping. |
| `IN_PUSHER_EXTENDED` | BOOL | Canonical pusher-extended input after physical/simulation mapping. |
| `IN_PUSHER_RETRACTED` | BOOL | Canonical pusher-retracted input after physical/simulation mapping. |
| `IN_DOWNSTREAM_CLEAR` | BOOL | Canonical downstream-clear input after physical/simulation mapping. |
| `FIRST_SCAN_DONE` | BOOL | Prevents repeated power-up initialization. |
| `ALL_SAFE` | BOOL | Safety permissive: E-stop healthy and guard closed. |
| `START_RISE` | BOOL | One-scan pulse on `IN_CYCLE_START` rising edge. |
| `START_LAST` | BOOL | Previous scan value for `IN_CYCLE_START`. |
| `RESET_RISE` | BOOL | One-scan pulse on `IN_RESET_PB` rising edge. |
| `RESET_LAST` | BOOL | Previous scan value for `IN_RESET_PB`. |
| `UNIT_RISE` | BOOL | One-scan pulse on `IN_UNIT_AT_INSPECTION` rising edge. |
| `UNIT_LAST` | BOOL | Previous scan value for `IN_UNIT_AT_INSPECTION`. |
| `VISION_LAST` | BOOL | Previous stable-monitor scan value for `IN_VISION_PASS`. |
| `VISION_CHANGED` | BOOL | Vision result changed while valid during inspection. |
| `VISION_UNSTABLE_LATCH` | BOOL | Vision changed after stability monitoring started. |
| `RESULT_LATCHED` | BOOL | Current unit result has been latched. |
| `RESULT_PASS_LATCH` | BOOL | Latched pass result for current/last unit. |
| `RESULT_FAIL_LATCH` | BOOL | Latched fail result for current/last unit. |
| `COMPLETE_PULSE` | BOOL | One-scan pulse when a unit finishes. |
| `PASS_COMPLETE_PULSE` | BOOL | One-scan pulse when a pass cycle finishes. |
| `FAIL_COMPLETE_PULSE` | BOOL | One-scan pulse when a reject cycle finishes. |
| `EXTEND_DEMAND` | BOOL | Internal command request for pusher extension. |
| `RETRACT_DEMAND` | BOOL | Internal command request for pusher retraction. |
| `OUTPUT_CONFLICT` | BOOL | Extend and retract demands are simultaneously true. |
| `FAULT_ESTOP` | BOOL | Latched E-stop fault. |
| `FAULT_GUARD` | BOOL | Latched guard-open-during-pusher fault. |
| `FAULT_EXTEND_TIMEOUT` | BOOL | Latched pusher extend timeout. |
| `FAULT_RETRACT_TIMEOUT` | BOOL | Latched pusher retract timeout. |
| `FAULT_UNIT_STUCK` | BOOL | Latched unit sensor stuck-high fault. |
| `FAULT_VISION_UNSTABLE` | BOOL | Latched vision instability fault. |
| `FAULT_OUTPUT_CONFLICT` | BOOL | Latched output conflict fault. |
| `UNIT_RELEASE_MONITOR` | BOOL | Set when a cycle completes and reset when the inspection sensor drops. |

## Timers

| Timer Tag | Type | Preset | Starts When |
|---|---|---:|---|
| `T_VISION_STABLE` | TON | 250 ms | `S_INSPECTING` and `IN_VISION_RESULT_VALID` and result unchanged. |
| `T_VISION_UNSTABLE` | TON | 1000 ms | `S_INSPECTING` and `IN_VISION_RESULT_VALID` and repeated result changes. |
| `T_PASS_RELEASE` | TON | 500 ms | `S_PASS_RELEASE`. |
| `T_EXTEND_TIMEOUT` | TON | 1500 ms | `S_REJECT_EXTEND` and not `IN_PUSHER_EXTENDED`. |
| `T_REJECT_SETTLE` | TON | 250 ms | `S_REJECT_EXTEND` and `IN_PUSHER_EXTENDED`. |
| `T_RETRACT_TIMEOUT` | TON | 1500 ms | `S_REJECT_RETRACT` and not `IN_PUSHER_RETRACTED`. |
| `T_UNIT_STUCK` | TON | 3000 ms | Cycle complete and `IN_UNIT_AT_INSPECTION` remains true. |

## Data Words

| Internal/Register Tag | Type | Purpose |
|---|---|---|
| `IN_UNIT_SERIAL` | UINT | Canonical serial input after physical/simulation mapping. |
| `IN_FAIL_REASON` | UINT | Canonical fail-reason input after physical/simulation mapping. |
| `CURRENT_SERIAL` | UINT | Captured `IN_UNIT_SERIAL` for active unit. |
| `CURRENT_FAIL_REASON` | UINT | Captured `IN_FAIL_REASON` for active failed unit. |
| `CYCLE_START_MS` | UDINT | Millisecond timestamp captured on unit arrival. |
| `NOW_MS` | UDINT | Current runtime millisecond counter. |

## Contact Notation

- `NO X` means normally-open contact of `X`; true when `X` is true.
- `NC X` means normally-closed contact of `X`; true when `X` is false.
- `SET X` means latch/set coil.
- `RST X` means reset/unlatch coil.
- `OTE X` means normal output coil.
- Rungs that assign the same coil must be implemented with set/reset coils where noted, not duplicate normal coils.

## Rungs

### Input Mapping

The ladder sequence must use canonical `IN_*` tags rather than reading raw field or simulation inputs directly.

| Rung | Logic | Coil/Action |
|---:|---|---|
| A1 | `NC SIM_MODE` and `NO UNIT_AT_INSPECTION`, or `NO SIM_MODE` and `NO SIM_UNIT_AT_INSPECTION` | `OTE IN_UNIT_AT_INSPECTION` |
| A2 | `NC SIM_MODE` and `NO UNIT_AT_REJECT`, or `NO SIM_MODE` and `NO SIM_UNIT_AT_REJECT` | `OTE IN_UNIT_AT_REJECT` |
| A3 | `NC SIM_MODE` and `NO VISION_PASS`, or `NO SIM_MODE` and `NO SIM_VISION_PASS` | `OTE IN_VISION_PASS` |
| A4 | `NC SIM_MODE` and `NO VISION_RESULT_VALID`, or `NO SIM_MODE` and `NO SIM_VISION_RESULT_VALID` | `OTE IN_VISION_RESULT_VALID` |
| A5 | `NC SIM_MODE` and `NO ESTOP_OK_NC`, or `NO SIM_MODE` and `NO SIM_ESTOP_OK_NC` | `OTE IN_ESTOP_OK_NC` |
| A6 | `NC SIM_MODE` and `NO GUARD_CLOSED_NC`, or `NO SIM_MODE` and `NO SIM_GUARD_CLOSED_NC` | `OTE IN_GUARD_CLOSED_NC` |
| A7 | `NC SIM_MODE` and `NO AUTO_MODE`, or `NO SIM_MODE` and `NO SIM_AUTO_MODE` | `OTE IN_AUTO_MODE` |
| A8 | `NC SIM_MODE` and `NO CYCLE_START`, or `NO SIM_MODE` and `NO SIM_CYCLE_START` | `OTE IN_CYCLE_START` |
| A9 | `NC SIM_MODE` and `NO RESET_PB`, or `NO SIM_MODE` and `NO SIM_RESET_PB` | `OTE IN_RESET_PB` |
| A10 | `NC SIM_MODE` and `NO PUSHER_EXTENDED`, or `NO SIM_MODE` and `NO SIM_PUSHER_EXTENDED` | `OTE IN_PUSHER_EXTENDED` |
| A11 | `NC SIM_MODE` and `NO PUSHER_RETRACTED`, or `NO SIM_MODE` and `NO SIM_PUSHER_RETRACTED` | `OTE IN_PUSHER_RETRACTED` |
| A12 | `NC SIM_MODE` and `NO DOWNSTREAM_CLEAR`, or `NO SIM_MODE` and `NO SIM_DOWNSTREAM_CLEAR` | `OTE IN_DOWNSTREAM_CLEAR` |

Map `IN_UNIT_SERIAL` and `IN_FAIL_REASON` in ST:

```iecst
IF SIM_MODE THEN
    IN_UNIT_SERIAL := SIM_UNIT_SERIAL_IN;
    IN_FAIL_REASON := SIM_FAIL_REASON_IN;
ELSE
    IN_UNIT_SERIAL := UNIT_SERIAL_IN;
    IN_FAIL_REASON := FAIL_REASON_IN;
END_IF;
```

### Power-Up And Edge Detection

| Rung | Logic | Coil/Action |
|---:|---|---|
| 1 | `NC FIRST_SCAN_DONE` | `SET S_IDLE`; `RST S_READY`; `RST S_INSPECTING`; `RST S_PASS_RELEASE`; `RST S_REJECT_EXTEND`; `RST S_REJECT_RETRACT`; `RST S_FAULT`; `SET FIRST_SCAN_DONE` |
| 2 | `NO IN_CYCLE_START` and `NC START_LAST` | `OTE START_RISE` |
| 3 | `NO IN_CYCLE_START` | `OTE START_LAST` |
| 4 | `NO IN_RESET_PB` and `NC RESET_LAST` | `OTE RESET_RISE` |
| 5 | `NO IN_RESET_PB` | `OTE RESET_LAST` |
| 6 | `NO IN_UNIT_AT_INSPECTION` and `NC UNIT_LAST` | `OTE UNIT_RISE` |
| 7 | `NO IN_UNIT_AT_INSPECTION` | `OTE UNIT_LAST` |

### Safety And Fault Latches

| Rung | Logic | Coil/Action |
|---:|---|---|
| 8 | `NO IN_ESTOP_OK_NC` and `NO IN_GUARD_CLOSED_NC` | `OTE ALL_SAFE` |
| 9 | `NC IN_ESTOP_OK_NC` | `SET FAULT_ESTOP`; `SET S_FAULT`; reset all non-fault state bits |
| 10 | `NO S_REJECT_EXTEND` and `NC IN_GUARD_CLOSED_NC` | `SET FAULT_GUARD`; `SET S_FAULT`; reset all non-fault state bits |
| 11 | `NO T_EXTEND_TIMEOUT.Q` | `SET FAULT_EXTEND_TIMEOUT`; `SET S_FAULT`; reset all non-fault state bits |
| 12 | `NO T_RETRACT_TIMEOUT.Q` | `SET FAULT_RETRACT_TIMEOUT`; `SET S_FAULT`; reset all non-fault state bits |
| 13 | `NO T_UNIT_STUCK.Q` | `SET FAULT_UNIT_STUCK`; `SET S_FAULT`; reset all non-fault state bits |
| 14 | `NO T_VISION_UNSTABLE.Q` | `SET FAULT_VISION_UNSTABLE`; `SET S_FAULT`; reset all non-fault state bits |
| 15 | `NO OUTPUT_CONFLICT` | `SET FAULT_OUTPUT_CONFLICT`; `SET S_FAULT`; reset all non-fault state bits |
| 16 | Any `FAULT_*` bit true | `SET S_FAULT`; reset `S_IDLE`, `S_READY`, `S_INSPECTING`, `S_PASS_RELEASE`, `S_REJECT_EXTEND`, `S_REJECT_RETRACT` |
| 17 | `NO S_FAULT` | Outputs must be suppressed by output rungs; do not rely only on state reset. |

### Reset Logic

| Rung | Logic | Coil/Action |
|---:|---|---|
| 18 | `NO S_FAULT` and `NO RESET_RISE` and `NO IN_ESTOP_OK_NC` and `NO IN_GUARD_CLOSED_NC` and `NO IN_AUTO_MODE` and `NO IN_PUSHER_RETRACTED` | `RST FAULT_ESTOP`; `RST FAULT_GUARD`; `RST FAULT_EXTEND_TIMEOUT`; `RST FAULT_RETRACT_TIMEOUT`; `RST FAULT_UNIT_STUCK`; `RST FAULT_VISION_UNSTABLE`; `RST FAULT_OUTPUT_CONFLICT`; `RST S_FAULT`; `SET S_IDLE` |
| 19 | `NO IN_RESET_PB` and `NO S_FAULT` | No action. This rung is intentionally documented to prove reset is edge-triggered by rung 18 and does not level-clear. |

### State Transitions

| Rung | Logic | Coil/Action |
|---:|---|---|
| 20 | `NO S_IDLE` and `NO IN_AUTO_MODE` and `NO START_RISE` and `NO ALL_SAFE` and `NO IN_PUSHER_RETRACTED` | `RST S_IDLE`; `SET S_READY` |
| 21 | `NO S_READY` and `NC IN_AUTO_MODE` | `RST S_READY`; `SET S_IDLE` |
| 22 | `NO S_READY` and `NO UNIT_RISE` and `NO ALL_SAFE` | `RST S_READY`; `SET S_INSPECTING`; `RST RESULT_LATCHED`; `RST RESULT_PASS_LATCH`; `RST RESULT_FAIL_LATCH` |
| 23 | `NO S_INSPECTING` and `NO T_VISION_STABLE.Q` and `NO IN_VISION_PASS` and `NC RESULT_LATCHED` | `SET RESULT_LATCHED`; `SET RESULT_PASS_LATCH`; `RST RESULT_FAIL_LATCH`; `RST S_INSPECTING`; `SET S_PASS_RELEASE` |
| 24 | `NO S_INSPECTING` and `NO T_VISION_STABLE.Q` and `NC IN_VISION_PASS` and `NC RESULT_LATCHED` | `SET RESULT_LATCHED`; `SET RESULT_FAIL_LATCH`; `RST RESULT_PASS_LATCH`; `RST S_INSPECTING`; `SET S_REJECT_EXTEND` |
| 25 | `NO S_PASS_RELEASE` and `NO T_PASS_RELEASE.Q` and `NO IN_DOWNSTREAM_CLEAR` | `SET PASS_COMPLETE_PULSE`; `SET COMPLETE_PULSE`; `SET UNIT_RELEASE_MONITOR`; `RST S_PASS_RELEASE`; `SET S_READY` |
| 26 | `NO S_REJECT_EXTEND` and `NO IN_PUSHER_EXTENDED` and `NO T_REJECT_SETTLE.Q` | `RST S_REJECT_EXTEND`; `SET S_REJECT_RETRACT` |
| 27 | `NO S_REJECT_RETRACT` and `NO IN_PUSHER_RETRACTED` | `SET FAIL_COMPLETE_PULSE`; `SET COMPLETE_PULSE`; `SET UNIT_RELEASE_MONITOR`; `RST S_REJECT_RETRACT`; `SET S_READY` |

### Vision Stability

| Rung | Logic | Coil/Action |
|---:|---|---|
| 28 | `NO S_INSPECTING` and `NO IN_VISION_RESULT_VALID` and `IN_VISION_PASS changed from VISION_LAST` | `SET VISION_CHANGED`; `SET VISION_UNSTABLE_LATCH` |
| 29 | `NO S_INSPECTING` and `NO IN_VISION_RESULT_VALID` and `NC VISION_CHANGED` | Run `T_VISION_STABLE` |
| 30 | `NO S_INSPECTING` and `NO IN_VISION_RESULT_VALID` and `NO VISION_UNSTABLE_LATCH` | Run `T_VISION_UNSTABLE` |
| 31 | `NO S_INSPECTING` | Copy `IN_VISION_PASS` to `VISION_LAST` at end of scan |
| 32 | `NC S_INSPECTING` | `RST VISION_CHANGED`; `RST VISION_UNSTABLE_LATCH`; reset `T_VISION_STABLE`; reset `T_VISION_UNSTABLE` |

If OpenPLC Editor makes the "changed from previous scan" portion awkward in pure ladder, implement it with two contacts:

- Set `VISION_CHANGED` when `IN_VISION_PASS` is true and `VISION_LAST` is false.
- Set `VISION_CHANGED` when `IN_VISION_PASS` is false and `VISION_LAST` is true.

### Timers

| Rung | Logic | Timer |
|---:|---|---|
| 33 | `NO S_PASS_RELEASE` | `TON T_PASS_RELEASE`, preset `500 ms` |
| 34 | `NO S_REJECT_EXTEND` and `NC IN_PUSHER_EXTENDED` | `TON T_EXTEND_TIMEOUT`, preset `1500 ms` |
| 35 | `NO S_REJECT_EXTEND` and `NO IN_PUSHER_EXTENDED` | `TON T_REJECT_SETTLE`, preset `250 ms` |
| 36 | `NO S_REJECT_RETRACT` and `NC IN_PUSHER_RETRACTED` | `TON T_RETRACT_TIMEOUT`, preset `1500 ms` |
| 37 | `NO UNIT_RELEASE_MONITOR` and `NO IN_UNIT_AT_INSPECTION` | `TON T_UNIT_STUCK`, preset `3000 ms` |
| 37A | `NO UNIT_RELEASE_MONITOR` and `NC IN_UNIT_AT_INSPECTION` | `RST UNIT_RELEASE_MONITOR`; reset `T_UNIT_STUCK` |

### Completion Pulses And Counters

| Rung | Logic | Coil/Action |
|---:|---|---|
| 38 | `NO PASS_COMPLETE_PULSE` | Increment `TOTAL_UNITS` by 1. Copy result/status words in ST. |
| 39 | `NO FAIL_COMPLETE_PULSE` | Increment `TOTAL_UNITS` by 1. Increment `TOTAL_REJECTS` by 1. Copy result/status words in ST. |
| 40 | End of scan | `RST PASS_COMPLETE_PULSE`; `RST FAIL_COMPLETE_PULSE`; `RST COMPLETE_PULSE` |

### Pusher Demand And Hard Interlock

| Rung | Logic | Coil/Action |
|---:|---|---|
| 41 | `NO S_REJECT_EXTEND` and `NO ALL_SAFE` and `NC IN_PUSHER_EXTENDED` | `OTE EXTEND_DEMAND` |
| 42 | `NO S_REJECT_RETRACT` and `NO IN_ESTOP_OK_NC` and `NC IN_PUSHER_RETRACTED` | `OTE RETRACT_DEMAND` |
| 43 | `NO EXTEND_DEMAND` and `NO RETRACT_DEMAND` | `OTE OUTPUT_CONFLICT` |
| 44 | `NO EXTEND_DEMAND` and `NC RETRACT_DEMAND` and `NC S_FAULT` and `NO IN_ESTOP_OK_NC` and `NO IN_GUARD_CLOSED_NC` | `OTE PUSHER_EXTEND` |
| 45 | `NO RETRACT_DEMAND` and `NC EXTEND_DEMAND` and `NC S_FAULT` and `NO IN_ESTOP_OK_NC` | `OTE PUSHER_RETRACT` |

### Conveyor And Indicators

| Rung | Logic | Coil/Action |
|---:|---|---|
| 46 | `NC S_FAULT` and `NO ALL_SAFE` and (`NO S_READY` or (`NO S_PASS_RELEASE` and `NO IN_DOWNSTREAM_CLEAR`)) | `OTE CONVEYOR_RUN` |
| 47 | `NO S_READY` and `NC S_FAULT` and `NO ALL_SAFE` and `NO IN_AUTO_MODE` | `OTE STATION_READY` |
| 48 | `NO RESULT_PASS_LATCH` and `NC S_FAULT` | `OTE PASS_LAMP` |
| 49 | `NO RESULT_FAIL_LATCH` and `NC S_FAULT` | `OTE FAIL_LAMP` |
| 50 | `NO S_FAULT` | `OTE FAULT_LAMP` |

### Status Register Updates

Use a small Structured Text section or OpenPLC ST program block for register/status assignments that are awkward in ladder:

```iecst
IF S_IDLE THEN
    STATE_CODE := 0;
ELSIF S_READY THEN
    STATE_CODE := 10;
ELSIF S_INSPECTING THEN
    STATE_CODE := 20;
ELSIF S_PASS_RELEASE THEN
    STATE_CODE := 30;
ELSIF S_REJECT_EXTEND THEN
    STATE_CODE := 40;
ELSIF S_REJECT_RETRACT THEN
    STATE_CODE := 50;
ELSIF S_FAULT THEN
    STATE_CODE := 90;
END_IF;

IF UNIT_RISE THEN
    CURRENT_SERIAL := IN_UNIT_SERIAL;
    CYCLE_START_MS := NOW_MS;
END_IF;

IF RESULT_FAIL_LATCH AND NOT RESULT_PASS_LATCH THEN
    CURRENT_FAIL_REASON := IN_FAIL_REASON;
ELSIF RESULT_PASS_LATCH THEN
    CURRENT_FAIL_REASON := 0;
END_IF;

IF COMPLETE_PULSE THEN
    LAST_SERIAL := CURRENT_SERIAL;
    LAST_CYCLE_TIME_MS := NOW_MS - CYCLE_START_MS;

    IF PASS_COMPLETE_PULSE THEN
        LAST_RESULT := 1;
        LAST_FAIL_REASON := 0;
    ELSIF FAIL_COMPLETE_PULSE THEN
        LAST_RESULT := 2;
        LAST_FAIL_REASON := CURRENT_FAIL_REASON;
    END_IF;
END_IF;

IF FAULT_ESTOP THEN
    FAULT_CODE := 100;
ELSIF FAULT_GUARD THEN
    FAULT_CODE := 110;
ELSIF FAULT_EXTEND_TIMEOUT THEN
    FAULT_CODE := 120;
ELSIF FAULT_RETRACT_TIMEOUT THEN
    FAULT_CODE := 130;
ELSIF FAULT_UNIT_STUCK THEN
    FAULT_CODE := 140;
ELSIF FAULT_VISION_UNSTABLE THEN
    FAULT_CODE := 150;
ELSIF FAULT_OUTPUT_CONFLICT THEN
    FAULT_CODE := 160;
ELSE
    FAULT_CODE := 0;
END_IF;
```

`NOW_MS` may be implemented with the OpenPLC runtime time source available in the selected project. If millisecond runtime access is awkward, use a free-running TON/counter approximation and record the limitation in `README.md`.

## Manual Transcription Checklist

- Confirm every external address matches `plc/io_map.md`.
- Confirm `IN_ESTOP_OK_NC` and `IN_GUARD_CLOSED_NC` are treated as healthy-high.
- Confirm output rungs include safety contacts and fault suppression, not only state bits.
- Confirm reset is driven by `RESET_RISE`, not `IN_RESET_PB`.
- Confirm pusher extend/retract commands use both state sequencing and hard mutual exclusion.
- Export both `plc/inspection_station.st` and `plc/inspection_station.xml` after drawing the program.
