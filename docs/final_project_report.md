# Automated Inspection and Reject Station

## Final Implementation Report

## 1. Project Summary

This project implements a simulated automated inspection station in OpenPLC. A unit enters the inspection area, receives a stable vision result, and is either released downstream or rejected by a pusher. The controller publishes status and traceability data over Modbus TCP, while a Python harness drives simulation inputs and records completed units in SQLite.

The implementation is intended as a portfolio-grade controls and systems-integration project. It combines IEC 61131-3 ladder logic, a Docker-hosted OpenPLC Runtime, Modbus TCP, Python test automation, and SQL-backed unit records.

## 2. Architecture

```text
Python harness / live traceability runner
        |
        | Modbus TCP, host port 1502
        v
OpenPLC Runtime v4 in Docker
        |
        | OpenPLC ladder program: main
        v
State machine, safety interlocks, telemetry registers
        |
        +-- Simulation coils/registers (SIM_*)
        +-- Output coils and holding-register status
        +-- SQLite traceability records
```

### Major Components

| Component | Responsibility |
|---|---|
| OpenPLC Editor | Owns the `main` ladder POU and all mapped variables. |
| OpenPLC Runtime v4 | Executes the PLC scan cycle in Docker. |
| Modbus slave plugin | Exposes runtime coils and holding registers. Docker host port `1502` maps to runtime port `502`. |
| `harness/modbus_client.py` | Maps named signals to Modbus addresses and hides raw address handling from tests. |
| `harness/scenarios.py` | Defines the 24 simulator-backed functional, safety, timing, and traceability scenarios. |
| `traceability/logger.py` | Observes completed-unit counters and inserts unit records into SQLite. |
| `harness/live_traceability.py` | Runs one live pass and reject cycle and persists their records for demonstration. |

## 3. PLC Behavior

### State Machine

| Code | State | Purpose |
|---:|---|---|
| 0 | `IDLE` | Station is stopped and outputs are safe. |
| 10 | `READY` | Safety permissives are healthy; conveyor is available for a new unit. |
| 20 | `INSPECTING` | Conveyor is stopped while vision data stabilizes. |
| 30 | `PASS_RELEASE` | Passed unit is released downstream. |
| 40 | `REJECT_EXTEND` | Pusher extends to reject a failed unit. |
| 50 | `REJECT_RETRACT` | Pusher returns to its home position. |
| 90 | `FAULT` | Motion is disabled until a permitted reset. |

The active ladder program stores the current state in `STATE_CODE`, so test clients can observe state without relying on the graphical debugger.

### Safety and Fault Handling

| Fault code | Condition | Verified response |
|---:|---|---|
| 100 | E-stop circuit unsafe | All motion drops and fault latches. |
| 110 | Guard open | Station inhibits motion and latches a guard fault. |
| 120 | Pusher does not extend in time | Motion drops and extend-timeout fault latches. |
| 130 | Pusher does not retract in time | Motion drops and retract-timeout fault latches. |
| 140 | Unit-present sensor remains high | Unit-stuck fault latches. |
| 150 | Vision result flickers beyond the allowed window | Unstable-vision fault latches. |
| 160 | Extend and retract commands conflict | Both outputs are inhibited and a conflict fault latches. |

The E-stop and guard signals use normally-closed, healthy-high semantics. A false E-stop signal is treated as a pressed E-stop, broken wire, or unsafe condition.

### Traceability and Telemetry

The controller exposes the following holding registers through Modbus:

| Register | Meaning |
|---|---|
| `STATE_CODE` | Current state-machine code. |
| `TOTAL_UNITS` | Completed-unit counter. |
| `TOTAL_REJECTS` | Rejected-unit counter. |
| `FAULT_CODE` | Latched fault reason. |
| `LAST_SERIAL` | Last completed unit serial. |
| `LAST_RESULT` | `1` for pass, `2` for fail. |
| `LAST_FAIL_REASON` | Failure classification for the last rejected unit. |

The Python logger measures elapsed time from unit entry to completion and stores that host-observed duration as `cycle_time_ms` in SQLite. This is the measured traceability time used by the live demonstration. `LAST_CYCLE_TIME_MS` remains reserved in the PLC map for a future controller-native cycle-time implementation.

## 4. Verification Evidence

### Simulator Regression Suite

The reviewed simulator run completed all 24 defined scenarios successfully:

```text
24 passed / 24 total
```

Coverage includes happy paths, E-stop and guard trips, reset behavior, pusher timeouts, stuck sensors, vision instability, timing checks, duplicate-record prevention, reject-reason logging, and counter-to-SQLite reconciliation. The generated raw results are retained in `docs/results.md` and `reports/results.csv`.

### Live OpenPLC Evidence

The live runtime was connected through Modbus TCP at `localhost:1502`. The following was verified against the running PLC:

| Test | Observed result |
|---|---|
| Ready-state telemetry | `STATE_CODE=10`, `FAULT_CODE=0`. |
| Pass cycle | `TOTAL_UNITS` incremented, serial `1001`, result `1`, no fault. |
| Reject cycle | `TOTAL_UNITS` and `TOTAL_REJECTS` incremented, serial `2002`, result `2`, failure reason `1`, returned to Ready. |
| E-stop, guard, pusher extend timeout, pusher retract timeout, and unstable vision | Fault lamp activated and motion outputs dropped. |
| Live traceability | Pass serial `51001` logged with `833 ms`; fail serial `51002` logged with `vision_defect` and `753 ms`. |

The final live traceability demonstration reported `TOTAL_UNITS=8` and `TOTAL_REJECTS=4`, reflecting repeated validation cycles. SQLite contained the two demo records identified above.

## 5. Key Defects Found and Corrected

Integration testing exposed and corrected several genuine control and integration defects:

1. Source-state resets executed before destination-state sets, causing scan-order transition failures.
2. Conveyor logic used competing output writers instead of one branch-based rung.
3. The unstable-vision timer was bound to the wrong generated timer instance.
4. The completion pulse was overwritten by the alternate path before the unit counter evaluated it.
5. Simulation serial/failure-reason values were not initially mapped into canonical PLC inputs.
6. The harness reset the failure reason after assigning it for a reject cycle.

These findings demonstrate why observable state, named Modbus signals, and repeatable scenario tests are useful even for a compact station.

## 6. How This Project Should Be Documented

Keep the documentation separated by purpose and update the relevant source whenever behavior changes:

| Document | Purpose | Update when |
|---|---|---|
| `plc/io_map.md` | Authoritative I/O, Modbus, state-code, and fault-code mapping. | A tag, address, code, or timing changes. |
| `docs/state_machine.md` | Operational state and safety behavior. | A state or transition changes. |
| `plc/ladder_rung_spec.md` | Reviewable ladder intent. | Rungs or ordering change. |
| `docs/test_plan.md` | Test coverage and expected outcomes. | A scenario is added or acceptance criteria change. |
| `docs/results.md` | Generated evidence from a reviewed run. | A suite is actually rerun. |
| This report | Architecture, evidence, limitations, and project narrative. | A significant implementation or validation milestone occurs. |

The important rule is to distinguish design intent, simulator verification, live-runtime verification, and hardware verification. Do not label simulated evidence as physical-hardware evidence.

## 7. Current Limitations and Recommended Improvements

1. The full 24-scenario suite has passed in the simulator; the live runtime has validated representative happy-path, safety, timeout, telemetry, and SQLite flows. Add live-run orchestration that resets/restarts the runtime per scenario before claiming a complete 24/24 live-runtime run.
2. Add an active authored Structured Text POU, such as a status/cycle-time block with explicitly shared global variables, if the resume must claim hand-authored Ladder and Structured Text logic. The current project is actively implemented in ladder; OpenPLC generates Structured Text during compilation.
3. Implement a controller-native `LAST_CYCLE_TIME_MS` value if an HMI or external client needs cycle timing directly from the PLC. The SQLite logger currently provides a verified host-measured duration.
4. Replace `serial` as the SQLite primary key with a generated event ID if the production system must retain multiple processing attempts for the same serial number.
5. Test the physical `%IX` and `%IW` paths with real I/O hardware before representing this as a field-hardware deployment.
6. Automate Modbus-plugin enablement after clean runtime uploads to remove the current Docker configuration step.

## 8. Reproduction Commands

Run simulator tests:

```bash
make test
.venv/bin/python -m harness.runner --backend sim --report
```

Run the live traceability demonstration after starting the runtime and enabling Modbus:

```bash
.venv/bin/python -m harness.live_traceability --host localhost --port 1502
```

## 9. Conclusion

The project delivers a complete simulated inspection-and-reject workflow with state-machine control, fail-safe interlocks, live Modbus observation, unit counters, and SQLite-backed unit traceability. The strongest evidence is the combination of a 24/24 simulator regression run and live PLC demonstrations of pass, reject, safety faults, telemetry, and database records.
