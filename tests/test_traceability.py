from pathlib import Path

from harness.modbus_client import StationClient
from harness.scenarios import ScenarioContext, run_fail_unit, run_pass_unit, start_station
from sim.io_simulator import InMemoryBackend
from traceability.logger import TraceabilityLogger


def test_traceability_rows_match_counters(tmp_path: Path) -> None:
    ctx = ScenarioContext(
        client=StationClient(InMemoryBackend()),
        logger=TraceabilityLogger(tmp_path / "traceability.sqlite3"),
    )
    start_station(ctx.client)
    run_pass_unit(ctx, 301)
    run_fail_unit(ctx, 302, fail_reason=3)
    rows = ctx.logger.rows()
    assert len(rows) == ctx.client.read_register("TOTAL_UNITS")
    assert sum(1 for row in rows if row["result"] == "FAIL") == ctx.client.read_register("TOTAL_REJECTS")

