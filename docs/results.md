# Harness Results

These results are generated from an actual harness run.

- Total scenarios: 24
- Passed: 24
- Failed: 0

| Scenario | Category | Result | Duration ms | Detail |
|---|---|---:|---:|---|
| Single pass unit, full cycle | happy_path | PASS | 838 | serial 1001 passed and logged |
| Single fail unit, full reject cycle | happy_path | PASS | 679 | serial 2001 rejected and logged |
| Ten consecutive passes | happy_path | PASS | 7825 | 10 pass records |
| Ten consecutive fails | happy_path | PASS | 6456 | 10 reject records |
| Alternating pass/fail | happy_path | PASS | 7187 | alternating sequence matched counts |
| Back-to-back units with minimum spacing | happy_path | PASS | 4713 | 6 close-spaced pass units |
| E-stop during INSPECTING | safety | PASS | 60 | E-stop faulted from INSPECTING |
| E-stop during REJECT_EXTEND | safety | PASS | 333 | E-stop faulted during pusher extension |
| E-stop wire break simulated | safety | PASS | 60 | healthy-high E-stop open caused fault |
| Guard door opened during pusher extend | safety | PASS | 322 | guard opening dropped pusher and faulted |
| Guard door opened while idle | safety | PASS | 166 | guard open blocked ready while idle |
| Reset held down continuously | safety | PASS | 264 | held reset did not repeatedly advance or clear |
| Reset pressed while E-stop still active | safety | PASS | 112 | reset ignored while E-stop remained active |
| Pusher extend confirmation never arrives | fault_handling | PASS | 1831 | extend timeout faulted |
| Pusher retract confirmation never arrives | fault_handling | PASS | 2094 | retract timeout faulted |
| Unit-present sensor stuck high | fault_handling | PASS | 3846 | stuck inspection sensor faulted |
| Inspection result changes mid-cycle | fault_handling | PASS | 1415 | unstable vision input faulted |
| Power-on state outputs safe on startup | fault_handling | PASS | 5 | startup state safe |
| Cycle time within bounds for pass | timing | PASS | 859 | pass cycle 796 ms |
| Cycle time within bounds for reject | timing | PASS | 697 | reject cycle 636 ms |
| Pusher stroke duration within bounds | timing | PASS | 756 | extend plus settle 422 ms |
| Every processed unit produces exactly one record | traceability | PASS | 2399 | 3 units produced 3 unique rows |
| Reject records carry a failure reason | traceability | PASS | 1337 | reject reasons persisted |
| Counter registers match record count in SQLite | traceability | PASS | 2090 | PLC counters matched SQLite counts |
