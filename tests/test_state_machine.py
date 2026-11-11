from pathlib import Path

from harness.modbus_client import StateCode, StationClient
from harness.scenarios import ScenarioContext, run_fail_unit, run_pass_unit, start_station
from sim.io_simulator import InMemoryBackend
from traceability.logger import TraceabilityLogger


def make_context(tmp_path: Path) -> ScenarioContext:
    return ScenarioContext(
        client=StationClient(InMemoryBackend()),
        logger=TraceabilityLogger(tmp_path / "traceability.sqlite3"),
    )


def test_single_pass_cycle_returns_ready(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    start_station(ctx.client)
    run_pass_unit(ctx, 101)
    assert ctx.client.read_register("STATE_CODE") == StateCode.READY
    assert ctx.client.read_register("TOTAL_UNITS") == 1
    assert ctx.client.read_register("TOTAL_REJECTS") == 0


def test_single_reject_cycle_returns_ready(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    start_station(ctx.client)
    run_fail_unit(ctx, 102, fail_reason=1)
    assert ctx.client.read_register("STATE_CODE") == StateCode.READY
    assert ctx.client.read_register("TOTAL_UNITS") == 1
    assert ctx.client.read_register("TOTAL_REJECTS") == 1

