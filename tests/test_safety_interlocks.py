from pathlib import Path

from harness.modbus_client import FaultCode, StateCode, StationClient
from harness.scenarios import ScenarioContext, enter_inspecting, start_station
from sim.io_simulator import InMemoryBackend
from traceability.logger import TraceabilityLogger


def make_context(tmp_path: Path) -> ScenarioContext:
    return ScenarioContext(
        client=StationClient(InMemoryBackend()),
        logger=TraceabilityLogger(tmp_path / "traceability.sqlite3"),
    )


def test_estop_faults_and_drops_outputs(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    start_station(ctx.client)
    enter_inspecting(ctx.client, 201)
    ctx.client.write_coil("SIM_ESTOP_OK_NC", False)
    assert ctx.client.read_register("STATE_CODE") == StateCode.FAULT
    assert ctx.client.read_register("FAULT_CODE") == FaultCode.ESTOP
    assert not ctx.client.read_coil("CONVEYOR_RUN")
    assert not ctx.client.read_coil("PUSHER_EXTEND")
    assert not ctx.client.read_coil("PUSHER_RETRACT")


def test_reset_requires_estop_restored(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    start_station(ctx.client)
    enter_inspecting(ctx.client, 202)
    ctx.client.write_coil("SIM_ESTOP_OK_NC", False)
    ctx.client.pulse("SIM_RESET_PB")
    assert ctx.client.read_register("STATE_CODE") == StateCode.FAULT
    ctx.client.write_coil("SIM_ESTOP_OK_NC", True)
    ctx.client.pulse("SIM_RESET_PB")
    assert ctx.client.read_register("STATE_CODE") == StateCode.IDLE

