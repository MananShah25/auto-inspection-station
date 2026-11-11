# Automated Inspection & Reject Station

A simulated PLC-controlled inspection and reject station, with an automated test harness and unit-level traceability.

A unit arrives at an inspection point and a vision result is latched. The PLC then either releases the unit downstream or rejects it with a pusher. The control logic is an IEC 61131-3 ladder program running on OpenPLC Runtime v4 in Docker. A Python/Pymodbus harness drives and verifies it over Modbus TCP, and every completed cycle is logged to SQLite.

**Scope.** This is an end-to-end software simulation. No physical hardware, camera or vision model was used. The vision result, photoeyes, pusher sensors, E-stop, guard and downstream-clear signals are simulated Modbus inputs. The OpenPLC runtime, Modbus link, ladder execution and SQLite writes are real software. It is an educational project and is not suitable for use in a real safety system.

## What I built

- **Control program:** a 7-state ladder logic program with 19 mapped field I/O points (12 inputs, 7 outputs). It has fail-safe normally-closed E-stop and guard inputs, confirmed pusher motion with timeouts, seven latched fault codes, and an edge-triggered reset that is gated on healthy permissives.
- **Modbus telemetry:** state, fault code, unit counters and last-unit registers are exposed as holding registers, so an external client can observe the station without a debugger.
- **Test plan and harness:** a 24-scenario test plan derived from the written spec, run by one Python suite against either an in-memory model or the live OpenPLC runtime.
- **Stateful property test:** a Hypothesis test that generates arbitrary input sequences and checks them against an oracle written from the spec. It found two defects the scenarios missed.
- **Traceability:** each completed cycle is stored in SQLite (serial, timestamp, result, failure reason, cycle time, station ID), with SQL queries for yield, reject reasons, cycle time and throughput.

## Results

| Check | Result | Scope |
| --- | --- | --- |
| 24-scenario suite | 24 of 24 pass | In-memory model (`--backend sim`), details in [docs/results.md](docs/results.md) |
| Pytest | 11 passed | 6 scenario-based tests plus 5 stateful and regression tests |
| Stateful test | No failures across 5 seeds of 5,000 sequences each | Model after the two fixes below |
| Live validation | Ready state, pass cycle, reject cycle, E-stop, guard, pusher extend and retract timeouts, unstable vision, counters, SQLite records | Representative subset against OpenPLC over Modbus TCP; the full 24 have not been run live |
| Live traceability records | Serial 51001 PASS in 833 ms; serial 51002 FAIL (`vision_defect`) in 753 ms | Written by `harness/live_traceability.py` |

## How the station works

```text
IDLE --start--> READY --unit arrives--> INSPECTING --stable pass--> PASS_RELEASE --released--> READY
                  ^                          |
                  |                     stable fail
                  |                          v
                  +--- retracted --- REJECT_RETRACT <--- extended --- REJECT_EXTEND

Any state --E-stop, guard, timeout, unstable vision, stuck sensor--> FAULT --reset--> IDLE
```

| Code | State | Code | Fault |
| --- | --- | --- | --- |
| 0 | IDLE | 100 | E-stop circuit unsafe |
| 10 | READY | 110 | Guard open during extension |
| 20 | INSPECTING | 120 | Pusher extend confirmation late (1500 ms) |
| 30 | PASS_RELEASE | 130 | Pusher retract confirmation late (1500 ms) |
| 40 | REJECT_EXTEND | 140 | Inspection sensor stuck high (3000 ms) |
| 50 | REJECT_RETRACT | 150 | Vision result unstable (1000 ms) |
| 90 | FAULT | 160 | Extend and retract commanded together |

A vision result must stay stable for 250 ms before it is latched. A fault stays latched until a reset rising edge arrives with E-stop, guard, auto mode and pusher-retracted all healthy. The full transition table is in [docs/state_machine.md](docs/state_machine.md).

## How it is verified

- **Spec first.** [docs/state_machine.md](docs/state_machine.md), [plc/io_map.md](plc/io_map.md) and [plc/ladder_rung_spec.md](plc/ladder_rung_spec.md) were written before the harness. Test expectations come from them.
- **Named signals only.** Scenarios use signal names such as `SIM_CYCLE_START` and `FAULT_CODE`. Raw Modbus addresses live only in `harness/modbus_client.py`.
- **One suite, two backends.** `--backend sim` runs against the in-memory model in `sim/io_simulator.py`. `--backend openplc` runs the same scenarios against the live runtime over Modbus TCP. Writable `SIM_*` coils and registers stand in for field inputs, which are read-only over Modbus.
- **Scenario plan.** The 24 scenarios fall into happy path (6), safety (7), fault handling (5), timing (3) and traceability (3). See [docs/test_plan.md](docs/test_plan.md).
- **Stateful property test.** `tests/test_station_stateful.py` generates input sequences on a fake clock and checks every step against the spec. The test itself was checked with eight hand-made one-line mutations of the model. Seven were caught, and the eighth was dead code, so it could not change behavior.

## Defects found

Details are in [docs/final_project_report.md](docs/final_project_report.md).

1. State transitions failed because the source state was reset before the destination state was set (scan order).
2. The conveyor had competing output writers; they were merged into one rung.
3. The unstable-vision fault was bound to the wrong generated timer instance.
4. A shared completion pulse was overwritten before the unit counter read it.
5. Simulated serial and failure-reason values were not mapped into the canonical PLC inputs.
6. The harness reset the failure reason after assigning it for a reject cycle.
7. The model ran the conveyor in `PASS_RELEASE` with downstream not clear (found by the stateful test).
8. The stuck-sensor timer overwrote an active E-stop fault code (100) with 140 (found by the stateful test).

Defects 7 and 8 were in the Python model, not the ladder program.

## Traceability

The logger polls the PLC total-units register and, when it increases, reads the last serial, result and failure reason, then inserts a row into SQLite. Schema: [traceability/schema.sql](traceability/schema.sql). Reports: [traceability/queries.sql](traceability/queries.sql) (yield, ranked reject reasons, mean and p95 cycle time, throughput per minute).

## Limitations

- Everything is simulated; no hardware was used.
- The 24 scenarios pass on the in-memory model. Only a representative subset has been run against the live PLC, and the model and ladder program are separate implementations.
- Fault 160 has no scenario because the model cannot produce that condition.
- Cycle time is measured on the host. The PLC's cycle-time register is reserved and not populated.
- `serial` is the primary key and the logger uses `INSERT OR REPLACE`, so a repeated serial overwrites its earlier row. Modbus registers are 16-bit, so serials must be 65535 or lower.
- The active control logic is ladder only. `plc/openplc_project/pous/programs/status_logic.st` is entirely commented out.
- Setting up the live OpenPLC runtime is manual; no compose file or Dockerfile is included.

## Repository layout

```text
plc/        I/O map, ladder rung spec, OpenPLC project, variable tables
harness/    Modbus client, scenarios, runner, assertions, report writer, live demo
sim/        In-memory model of the station
traceability/  SQLite schema, logger and queries
tests/      Pytest tests, including the stateful property test
docs/       State machine, test plan, results, final report
conf/       Modbus slave plugin configuration
```

## Setup and run

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Developed on Python 3.10.

```bash
.venv/bin/python -m pytest -q                              # all tests (about 25 s)
.venv/bin/python -m harness.runner --backend sim           # 24 scenarios on the model
.venv/bin/python -m harness.runner --backend sim --report  # also writes docs/results.md and reports/results.csv
```

Set `STATION_EXAMPLES` to change how many sequences the stateful test generates (default 1500).

### Against OpenPLC

Run OpenPLC Runtime v4 in Docker with host port 1502 mapped to the runtime's Modbus port 502. Load the program from `plc/openplc_project`, enable the `modbus_slave` runtime plugin, and start the PLC. After a clean build and upload, re-enable the plugin before connecting.

```bash
.venv/bin/python -m harness.runner --backend openplc --host localhost --port 1502 --unit-id 1
.venv/bin/python -m harness.live_traceability --host localhost --port 1502
```

The second command runs one live pass and one reject cycle and writes records to `traceability/live_traceability.sqlite3`.

## License

MIT, see [LICENSE](LICENSE). OpenPLC is a separate project with its own license, and no OpenPLC source code is included in this repository.
