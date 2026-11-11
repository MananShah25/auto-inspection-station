# Test Plan

The harness drives scenarios through named I/O signals from `harness.modbus_client`. It must not use raw Modbus addresses outside the client layer. Simulator runs are allowed for development, but `docs/results.md` may only contain scenarios that were actually executed.

## Assumptions

- Automated test mode enables `SIM_MODE` and writes only `SIM_*` signals.
- Safety inputs are healthy-high: E-stop OK, guard closed, and pusher retracted are true during normal startup.
- Timing assertions allow a scan/polling tolerance around nominal PLC timing.
- A scenario failure is valuable evidence. Do not suppress or skip it unless the scenario itself is invalid.

## Scenario Matrix

| ID | Scenario | Category | Stimulus Summary | Expected Outcome |
|---:|---|---|---|---|
| 1 | Single pass unit, full cycle | Happy path | Start station, present one unit, provide stable pass result, clear sensor. | Returns to `READY`, conveyor resumes, total units +1, rejects unchanged, pass lamp on. |
| 2 | Single fail unit, full reject cycle | Happy path | Present one unit, provide stable fail result/reason, confirm extend and retract. | Returns to `READY`, total units +1, rejects +1, fail lamp on, fail reason recorded. |
| 3 | Ten consecutive passes | Happy path | Repeat pass cycle for serials 1001-1010. | Ten new pass records, no rejects, no faults. |
| 4 | Ten consecutive fails | Happy path | Repeat fail cycle with pusher confirmations. | Ten new fail records, reject count increases by ten. |
| 5 | Alternating pass/fail | Happy path | Run pass/fail sequence alternating by serial. | Counts and traceability results match the sequence exactly. |
| 6 | Back-to-back units with minimum spacing | Happy path | Present next unit shortly after station returns to ready. | Every cycle completes once; no duplicate records. |
| 7 | E-stop during `INSPECTING` | Safety | Drop E-stop after inspection begins. | Immediate `FAULT`, all outputs off, fault code `100`. |
| 8 | E-stop during `REJECT_EXTEND` | Safety | Drop E-stop while pusher extend is commanded. | Immediate `FAULT`, pusher outputs off, fault code `100`. |
| 9 | E-stop wire break simulated | Safety | Start with E-stop input false. | Station never becomes ready; fault code `100`. |
| 10 | Guard door opened during pusher extend | Safety | Open guard during reject extension. | Extend drops, `FAULT`, fault code `110`. |
| 11 | Guard door opened while idle | Safety | Keep idle and open guard. | No pusher motion; station cannot enter ready. |
| 12 | Reset held down continuously | Safety | Hold reset high across multiple polls after a fault. | Fault clears only once when permitted; reset does not repeatedly clear. |
| 13 | Reset pressed while E-stop still active | Safety | Fault on E-stop, press reset before restoring E-stop. | Fault remains latched. |
| 14 | Pusher extend confirmation never arrives | Fault handling | Reject unit but never set extended confirmation. | Fault code `120`, no retry loop. |
| 15 | Pusher retract confirmation never arrives | Fault handling | Confirm extension but never confirm retract home. | Fault code `130`. |
| 16 | Unit-present sensor stuck high | Fault handling | Leave inspection sensor high after release. | Fault code `140` after stuck-high timeout. |
| 17 | Inspection result changes mid-cycle | Fault handling | Toggle pass/fail while vision-valid during inspection. | Stability timer restarts or faults with code `150` if unstable too long. |
| 18 | Power-on safe state | Fault handling | Inspect initial state before start. | State `IDLE`, outputs off, no pusher motion. |
| 19 | Pass cycle time within bounds | Timing | Run a nominal pass cycle. | `LAST_CYCLE_TIME_MS` within expected pass bounds. |
| 20 | Reject cycle time within bounds | Timing | Run a nominal reject cycle. | `LAST_CYCLE_TIME_MS` within expected reject bounds. |
| 21 | Pusher stroke duration within bounds | Timing | Measure reject extend/retract phases. | Stroke observations remain within configured bounds. |
| 22 | Exactly one record per unit | Traceability | Run multiple mixed units. | SQLite row count increases by completed unit count. |
| 23 | Reject records carry a failure reason | Traceability | Run failed units with explicit reasons. | Fail rows contain non-zero/non-null reason values. |
| 24 | PLC counters match SQLite records | Traceability | Compare final PLC counters to traceability DB. | `TOTAL_UNITS` equals row count; `TOTAL_REJECTS` equals fail row count. |

## Required Assertions

| Assertion | Purpose |
|---|---|
| `assert_output_state` | Verify named output coils are true/false as expected. |
| `assert_state_within` | Verify the PLC reaches a state within a timeout. |
| `assert_timing_between` | Verify measured scenario/cycle time bounds. |
| `assert_no_simultaneous_outputs` | Verify pusher extend and retract are never on together. |
| `assert_record_written` | Verify traceability row creation and contents. |

