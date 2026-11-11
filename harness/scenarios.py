from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from harness.assertions import (
    assert_no_simultaneous_outputs,
    assert_output_state,
    assert_record_written,
    assert_state_within,
    assert_timing_between,
)
from harness.modbus_client import FaultCode, StateCode, StationClient
from traceability.logger import TraceabilityLogger


@dataclass(frozen=True)
class Scenario:
    name: str
    category: str
    run: Callable[["ScenarioContext"], str]


@dataclass
class ScenarioContext:
    client: StationClient
    logger: TraceabilityLogger


def all_scenarios() -> list[Scenario]:
    return [
        Scenario("Single pass unit, full cycle", "happy_path", scenario_single_pass),
        Scenario("Single fail unit, full reject cycle", "happy_path", scenario_single_fail),
        Scenario("Ten consecutive passes", "happy_path", scenario_ten_passes),
        Scenario("Ten consecutive fails", "happy_path", scenario_ten_fails),
        Scenario("Alternating pass/fail", "happy_path", scenario_alternating),
        Scenario("Back-to-back units with minimum spacing", "happy_path", scenario_back_to_back),
        Scenario("E-stop during INSPECTING", "safety", scenario_estop_inspecting),
        Scenario("E-stop during REJECT_EXTEND", "safety", scenario_estop_reject_extend),
        Scenario("E-stop wire break simulated", "safety", scenario_estop_wire_break),
        Scenario("Guard door opened during pusher extend", "safety", scenario_guard_during_extend),
        Scenario("Guard door opened while idle", "safety", scenario_guard_idle),
        Scenario("Reset held down continuously", "safety", scenario_reset_held),
        Scenario("Reset pressed while E-stop still active", "safety", scenario_reset_while_estop),
        Scenario("Pusher extend confirmation never arrives", "fault_handling", scenario_extend_timeout),
        Scenario("Pusher retract confirmation never arrives", "fault_handling", scenario_retract_timeout),
        Scenario("Unit-present sensor stuck high", "fault_handling", scenario_unit_stuck_high),
        Scenario("Inspection result changes mid-cycle", "fault_handling", scenario_vision_unstable),
        Scenario("Power-on state outputs safe on startup", "fault_handling", scenario_power_on_safe),
        Scenario("Cycle time within bounds for pass", "timing", scenario_pass_timing),
        Scenario("Cycle time within bounds for reject", "timing", scenario_reject_timing),
        Scenario("Pusher stroke duration within bounds", "timing", scenario_pusher_stroke_timing),
        Scenario("Every processed unit produces exactly one record", "traceability", scenario_one_record_per_unit),
        Scenario("Reject records carry a failure reason", "traceability", scenario_reject_reason_records),
        Scenario("Counter registers match record count in SQLite", "traceability", scenario_counters_match_records),
    ]


def scenario_single_pass(ctx: ScenarioContext) -> str:
    start_station(ctx.client)
    run_pass_unit(ctx, 1001)
    assert_output_state(ctx.client, {"STATION_READY": True, "PASS_LAMP": True, "FAULT_LAMP": False})
    assert_record_written(ctx.logger.rows(), 1001, "PASS")
    return "serial 1001 passed and logged"


def scenario_single_fail(ctx: ScenarioContext) -> str:
    start_station(ctx.client)
    run_fail_unit(ctx, 2001, fail_reason=1)
    assert_output_state(ctx.client, {"STATION_READY": True, "FAIL_LAMP": True, "FAULT_LAMP": False})
    assert_record_written(ctx.logger.rows(), 2001, "FAIL")
    return "serial 2001 rejected and logged"


def scenario_ten_passes(ctx: ScenarioContext) -> str:
    start_station(ctx.client)
    for serial in range(3001, 3011):
        run_pass_unit(ctx, serial)
    units, rejects = ctx.logger.counts()
    assert units == 10
    assert rejects == 0
    return "10 pass records"


def scenario_ten_fails(ctx: ScenarioContext) -> str:
    start_station(ctx.client)
    for serial in range(4001, 4011):
        run_fail_unit(ctx, serial, fail_reason=2)
    units, rejects = ctx.logger.counts()
    assert units == 10
    assert rejects == 10
    return "10 reject records"


def scenario_alternating(ctx: ScenarioContext) -> str:
    start_station(ctx.client)
    for index, serial in enumerate(range(5001, 5011)):
        if index % 2 == 0:
            run_pass_unit(ctx, serial)
        else:
            run_fail_unit(ctx, serial, fail_reason=3)
    units, rejects = ctx.logger.counts()
    assert units == 10
    assert rejects == 5
    return "alternating sequence matched counts"


def scenario_back_to_back(ctx: ScenarioContext) -> str:
    start_station(ctx.client)
    for serial in range(6001, 6007):
        run_pass_unit(ctx, serial, settle_s=0.02)
    assert ctx.client.read_register("TOTAL_UNITS") == 6
    return "6 close-spaced pass units"


def scenario_estop_inspecting(ctx: ScenarioContext) -> str:
    start_station(ctx.client)
    enter_inspecting(ctx.client, 7001)
    ctx.client.write_coil("SIM_ESTOP_OK_NC", False)
    assert_state_within(ctx.client, StateCode.FAULT)
    assert ctx.client.read_register("FAULT_CODE") == FaultCode.ESTOP
    assert_all_outputs_safe(ctx.client)
    return "E-stop faulted from INSPECTING"


def scenario_estop_reject_extend(ctx: ScenarioContext) -> str:
    start_station(ctx.client)
    enter_reject_extend(ctx.client, 8001, fail_reason=1)
    ctx.client.write_coil("SIM_ESTOP_OK_NC", False)
    assert_state_within(ctx.client, StateCode.FAULT)
    assert ctx.client.read_register("FAULT_CODE") == FaultCode.ESTOP
    assert_all_outputs_safe(ctx.client)
    return "E-stop faulted during pusher extension"


def scenario_estop_wire_break(ctx: ScenarioContext) -> str:
    ctx.client.initialize_simulation_inputs()
    ctx.client.write_coil("SIM_ESTOP_OK_NC", False)
    ctx.client.pulse("SIM_CYCLE_START")
    assert_state_within(ctx.client, StateCode.FAULT)
    assert ctx.client.read_register("FAULT_CODE") == FaultCode.ESTOP
    assert_all_outputs_safe(ctx.client)
    return "healthy-high E-stop open caused fault"


def scenario_guard_during_extend(ctx: ScenarioContext) -> str:
    start_station(ctx.client)
    enter_reject_extend(ctx.client, 9001, fail_reason=2)
    ctx.client.write_coil("SIM_GUARD_CLOSED_NC", False)
    assert_state_within(ctx.client, StateCode.FAULT)
    assert ctx.client.read_register("FAULT_CODE") == FaultCode.GUARD
    assert_all_outputs_safe(ctx.client)
    return "guard opening dropped pusher and faulted"


def scenario_guard_idle(ctx: ScenarioContext) -> str:
    ctx.client.initialize_simulation_inputs()
    ctx.client.write_coil("SIM_GUARD_CLOSED_NC", False)
    ctx.client.pulse("SIM_CYCLE_START")
    time.sleep(0.1)
    assert ctx.client.read_register("STATE_CODE") == StateCode.IDLE
    assert_output_state(ctx.client, {"CONVEYOR_RUN": False, "PUSHER_EXTEND": False})
    return "guard open blocked ready while idle"


def scenario_reset_held(ctx: ScenarioContext) -> str:
    start_station(ctx.client)
    enter_inspecting(ctx.client, 10001)
    ctx.client.write_coil("SIM_ESTOP_OK_NC", False)
    assert_state_within(ctx.client, StateCode.FAULT)
    ctx.client.write_coil("SIM_ESTOP_OK_NC", True)
    ctx.client.write_coil("SIM_RESET_PB", True)
    assert_state_within(ctx.client, StateCode.IDLE)
    time.sleep(0.2)
    assert ctx.client.read_register("STATE_CODE") == StateCode.IDLE
    ctx.client.write_coil("SIM_RESET_PB", False)
    return "held reset did not repeatedly advance or clear"


def scenario_reset_while_estop(ctx: ScenarioContext) -> str:
    start_station(ctx.client)
    enter_inspecting(ctx.client, 11001)
    ctx.client.write_coil("SIM_ESTOP_OK_NC", False)
    assert_state_within(ctx.client, StateCode.FAULT)
    ctx.client.pulse("SIM_RESET_PB")
    assert ctx.client.read_register("FAULT_CODE") == FaultCode.ESTOP
    assert ctx.client.read_register("STATE_CODE") == StateCode.FAULT
    return "reset ignored while E-stop remained active"


def scenario_extend_timeout(ctx: ScenarioContext) -> str:
    start_station(ctx.client)
    enter_reject_extend(ctx.client, 12001, fail_reason=4)
    assert_state_within(ctx.client, StateCode.FAULT, timeout_s=2.2)
    assert ctx.client.read_register("FAULT_CODE") == FaultCode.EXTEND_TIMEOUT
    return "extend timeout faulted"


def scenario_retract_timeout(ctx: ScenarioContext) -> str:
    start_station(ctx.client)
    enter_reject_extend(ctx.client, 13001, fail_reason=4)
    ctx.client.write_coil("SIM_PUSHER_RETRACTED", False)
    ctx.client.write_coil("SIM_PUSHER_EXTENDED", True)
    assert_state_within(ctx.client, StateCode.REJECT_RETRACT)
    ctx.client.write_coil("SIM_PUSHER_EXTENDED", False)
    assert_state_within(ctx.client, StateCode.FAULT, timeout_s=2.2)
    assert ctx.client.read_register("FAULT_CODE") == FaultCode.RETRACT_TIMEOUT
    return "retract timeout faulted"


def scenario_unit_stuck_high(ctx: ScenarioContext) -> str:
    start_station(ctx.client)
    run_pass_unit(ctx, 14001, clear_unit=False)
    assert_state_within(ctx.client, StateCode.FAULT, timeout_s=3.8)
    assert ctx.client.read_register("FAULT_CODE") == FaultCode.UNIT_STUCK
    return "stuck inspection sensor faulted"


def scenario_vision_unstable(ctx: ScenarioContext) -> str:
    start_station(ctx.client)
    enter_inspecting(ctx.client, 15001)
    ctx.client.write_coil("SIM_VISION_RESULT_VALID", True)
    deadline = time.monotonic() + 1.3
    value = False
    while time.monotonic() < deadline:
        value = not value
        ctx.client.write_coil("SIM_VISION_PASS", value)
        time.sleep(0.08)
    assert_state_within(ctx.client, StateCode.FAULT, timeout_s=0.5)
    assert ctx.client.read_register("FAULT_CODE") == FaultCode.VISION_UNSTABLE
    return "unstable vision input faulted"


def scenario_power_on_safe(ctx: ScenarioContext) -> str:
    assert ctx.client.read_register("STATE_CODE") == StateCode.IDLE
    assert_all_outputs_safe(ctx.client)
    return "startup state safe"


def scenario_pass_timing(ctx: ScenarioContext) -> str:
    start_station(ctx.client)
    run_pass_unit(ctx, 16001)
    observed = ctx.client.read_register("LAST_CYCLE_TIME_MS")
    assert_timing_between("pass cycle", observed, 650, 1400)
    return f"pass cycle {observed} ms"


def scenario_reject_timing(ctx: ScenarioContext) -> str:
    start_station(ctx.client)
    run_fail_unit(ctx, 17001, fail_reason=1)
    observed = ctx.client.read_register("LAST_CYCLE_TIME_MS")
    assert_timing_between("reject cycle", observed, 550, 2200)
    return f"reject cycle {observed} ms"


def scenario_pusher_stroke_timing(ctx: ScenarioContext) -> str:
    start_station(ctx.client)
    enter_reject_extend(ctx.client, 18001, fail_reason=1)
    started = time.monotonic()
    ctx.client.write_coil("SIM_PUSHER_RETRACTED", False)
    time.sleep(0.15)
    ctx.client.write_coil("SIM_PUSHER_EXTENDED", True)
    assert_state_within(ctx.client, StateCode.REJECT_RETRACT)
    elapsed_ms = int((time.monotonic() - started) * 1000)
    assert_timing_between("pusher extend plus settle", elapsed_ms, 350, 900)
    return f"extend plus settle {elapsed_ms} ms"


def scenario_one_record_per_unit(ctx: ScenarioContext) -> str:
    start_station(ctx.client)
    for serial in (19001, 19002, 19003):
        run_pass_unit(ctx, serial)
    rows = ctx.logger.rows()
    assert len(rows) == 3
    assert len({row["serial"] for row in rows}) == 3
    return "3 units produced 3 unique rows"


def scenario_reject_reason_records(ctx: ScenarioContext) -> str:
    start_station(ctx.client)
    run_fail_unit(ctx, 20001, fail_reason=1)
    run_fail_unit(ctx, 20002, fail_reason=2)
    reasons = {row["fail_reason"] for row in ctx.logger.rows()}
    assert reasons == {"vision_defect", "dimension"}
    return "reject reasons persisted"


def scenario_counters_match_records(ctx: ScenarioContext) -> str:
    start_station(ctx.client)
    run_pass_unit(ctx, 21001)
    run_fail_unit(ctx, 21002, fail_reason=3)
    run_fail_unit(ctx, 21003, fail_reason=1)
    units, rejects = ctx.logger.counts()
    assert ctx.client.read_register("TOTAL_UNITS") == units
    assert ctx.client.read_register("TOTAL_REJECTS") == rejects
    return "PLC counters matched SQLite counts"


def start_station(client: StationClient) -> None:
    client.initialize_simulation_inputs()
    client.pulse("SIM_CYCLE_START")
    assert_state_within(client, StateCode.READY)


def enter_inspecting(client: StationClient, serial: int, fail_reason: int = 0) -> None:
    client.write_register("SIM_UNIT_SERIAL_IN", serial)
    client.write_register("SIM_FAIL_REASON_IN", fail_reason)
    client.write_coil("SIM_UNIT_AT_INSPECTION", True)
    assert_state_within(client, StateCode.INSPECTING)


def enter_reject_extend(client: StationClient, serial: int, fail_reason: int) -> None:
    enter_inspecting(client, serial, fail_reason)
    client.write_coil("SIM_VISION_PASS", False)
    client.write_coil("SIM_VISION_RESULT_VALID", True)
    assert_state_within(client, StateCode.REJECT_EXTEND)


def run_pass_unit(
    ctx: ScenarioContext,
    serial: int,
    settle_s: float = 0.05,
    clear_unit: bool = True,
) -> None:
    before = ctx.client.read_register("TOTAL_UNITS")
    ctx.logger.mark_cycle_started()
    enter_inspecting(ctx.client, serial)
    ctx.client.write_coil("SIM_VISION_PASS", True)
    ctx.client.write_coil("SIM_VISION_RESULT_VALID", True)
    assert_state_within(ctx.client, StateCode.PASS_RELEASE)
    if clear_unit:
        time.sleep(settle_s)
        ctx.client.write_coil("SIM_UNIT_AT_INSPECTION", False)
    assert_state_within(ctx.client, StateCode.READY, timeout_s=1.5)
    ctx.client.write_coil("SIM_VISION_RESULT_VALID", False)
    ctx.logger.poll(ctx.client)
    assert ctx.client.read_register("TOTAL_UNITS") == before + 1
    assert_no_simultaneous_outputs(ctx.client)


def run_fail_unit(ctx: ScenarioContext, serial: int, fail_reason: int, settle_s: float = 0.05) -> None:
    before_units = ctx.client.read_register("TOTAL_UNITS")
    before_rejects = ctx.client.read_register("TOTAL_REJECTS")
    ctx.logger.mark_cycle_started()
    enter_reject_extend(ctx.client, serial, fail_reason)
    ctx.client.write_coil("SIM_PUSHER_RETRACTED", False)
    time.sleep(settle_s)
    ctx.client.write_coil("SIM_PUSHER_EXTENDED", True)
    assert_state_within(ctx.client, StateCode.REJECT_RETRACT)
    ctx.client.write_coil("SIM_UNIT_AT_INSPECTION", False)
    ctx.client.write_coil("SIM_PUSHER_EXTENDED", False)
    time.sleep(settle_s)
    ctx.client.write_coil("SIM_PUSHER_RETRACTED", True)
    assert_state_within(ctx.client, StateCode.READY)
    ctx.client.write_coil("SIM_VISION_RESULT_VALID", False)
    ctx.logger.poll(ctx.client)
    assert ctx.client.read_register("TOTAL_UNITS") == before_units + 1
    assert ctx.client.read_register("TOTAL_REJECTS") == before_rejects + 1
    assert_no_simultaneous_outputs(ctx.client)


def assert_all_outputs_safe(client: StationClient) -> None:
    assert_output_state(
        client,
        {
            "CONVEYOR_RUN": False,
            "PUSHER_EXTEND": False,
            "PUSHER_RETRACT": False,
            "STATION_READY": False,
        },
    )
