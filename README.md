# Automated Inspection & Reject Station

Portfolio project for a simulated PLC-controlled inspection station with automated Modbus testing and traceable unit logging.

## What This Demonstrates

- PLC station design with a documented I/O map and state machine.
- Safety-oriented ladder logic specification for E-stop, guard door, pusher interlocks, reset behavior, and timeout faults.
- Python harness that drives scenarios through named Modbus signals.
- SQLite traceability records for serial, timestamp, result, failure reason, cycle time, and station ID.
- Simulator-backed tests so the harness can be developed before OpenPLC runtime setup is complete.

## Repository Layout

```text
plc/                  OpenPLC design artifacts and transcribable rung spec
harness/              Modbus client, assertions, scenarios, runner, reports
traceability/         SQLite schema, logger, and analysis queries
sim/                  In-memory simulator for fast harness development
tests/                Pytest coverage for simulator-backed behavior
docs/                 State machine, test plan, and generated results
```

## Current Status

Implemented:

- `plc/io_map.md`
- `docs/state_machine.md`
- `plc/ladder_rung_spec.md`
- `docs/test_plan.md`
- simulator-backed harness
- traceability logger/schema/queries
- report writer
- pytest checks

Pending manual OpenPLC gates:

- Install OpenPLC Editor and Runtime.
- Draw the ladder logic from `plc/ladder_rung_spec.md`.
- Export `plc/inspection_station.st` and `plc/inspection_station.xml`.
- Load the program into OpenPLC Runtime.
- Confirm Modbus TCP is reachable at `localhost:502`.
- Run the harness against `--backend openplc`.

## Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

The brief targets Python 3.11+, but the current code also runs under Python 3.10 on this machine.

## Run Tests

```bash
.venv/bin/python -m pytest -q
```

## Run Simulator Scenarios

```bash
.venv/bin/python -m harness.runner --backend sim
```

This prints a raw pass/fail table for all 24 scenarios. It does not write `docs/results.md` unless explicitly requested.

## Generate Reports

After reviewing raw output:

```bash
.venv/bin/python -m harness.runner --backend sim --report
```

This writes:

- `docs/results.md`
- `reports/results.csv`

Do not commit `docs/results.md` unless the run was actually executed and reviewed.

## Run Against OpenPLC

After OpenPLC Runtime is loaded and reachable:

```bash
.venv/bin/python -m harness.runner --backend openplc --host localhost --port 502 --unit-id 1
```

The harness uses the writable `SIM_*` Modbus layer defined in `plc/io_map.md` so tests can drive the PLC over Modbus without requiring writes to read-only `%IX` or `%IW` areas.

## Traceability Queries

The schema is in `traceability/schema.sql`; analysis examples are in `traceability/queries.sql`.

The logger writes rows when it observes `TOTAL_UNITS` increment and then reads:

- `LAST_SERIAL`
- `LAST_RESULT`
- `LAST_FAIL_REASON`
- `LAST_CYCLE_TIME_MS`

## Interview Talking Points

- Why normally-closed E-stop wiring is treated as healthy-high and fail-safe-low.
- Why a reset must be edge-triggered and permissive-gated.
- Why pusher extend and retract require a hard mutual exclusion interlock.
- Why the harness uses writable simulation coils/registers instead of trying to write `%IX`/`%IW`.
- How state, counters, and traceability records are observed through Modbus.
- How simulator-first testing reduces debugging risk before loading OpenPLC.

