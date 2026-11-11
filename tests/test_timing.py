from pathlib import Path

from harness.assertions import assert_timing_between
from harness.modbus_client import StationClient
from harness.scenarios import ScenarioContext, run_pass_unit, start_station
from sim.io_simulator import InMemoryBackend
from traceability.logger import TraceabilityLogger


def test_pass_cycle_timing_is_in_expected_range(tmp_path: Path) -> None:
    ctx = ScenarioContext(
        client=StationClient(InMemoryBackend()),
        logger=TraceabilityLogger(tmp_path / "traceability.sqlite3"),
    )
    start_station(ctx.client)
    run_pass_unit(ctx, 401)
    assert_timing_between("pass cycle", ctx.client.read_register("LAST_CYCLE_TIME_MS"), 650, 1400)

