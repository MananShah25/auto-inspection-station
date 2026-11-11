from __future__ import annotations

import time
from dataclasses import dataclass, field

from harness.modbus_client import COILS, HOLDING_REGISTERS, FaultCode, ResultCode, StateCode


VISION_STABLE_MS = 250
VISION_UNSTABLE_MS = 1000
PASS_RELEASE_MS = 500
PUSHER_EXTEND_TIMEOUT_MS = 1500
PUSHER_RETRACT_TIMEOUT_MS = 1500
REJECT_SETTLE_MS = 250
UNIT_STUCK_HIGH_MS = 3000


@dataclass
class InMemoryBackend:
    coils: dict[int, bool] = field(default_factory=dict)
    holding_registers: dict[int, int] = field(default_factory=dict)
    state_entered_ms: int = field(default_factory=lambda: _now_ms())
    cycle_start_ms: int = 0
    current_serial: int = 0
    current_fail_reason: int = 0
    vision_last: bool = False
    vision_stable_since_ms: int | None = None
    vision_unstable_since_ms: int | None = None
    unit_release_monitor_since_ms: int | None = None
    reject_settle_since_ms: int | None = None
    fault_latched: bool = False
    fault_code: FaultCode = FaultCode.NONE

    def __post_init__(self) -> None:
        for signal in COILS.values():
            self.coils.setdefault(signal.address, False)
        for signal in HOLDING_REGISTERS.values():
            self.holding_registers.setdefault(signal.address, 0)
        self._set_state(StateCode.IDLE)
        self._write_defaults()
        self._update_outputs()

    def read_coil(self, address: int) -> bool:
        self.tick()
        return bool(self.coils.get(address, False))

    def write_coil(self, address: int, value: bool) -> None:
        self.coils[address] = bool(value)
        self.tick()

    def read_holding_register(self, address: int) -> int:
        self.tick()
        return int(self.holding_registers.get(address, 0))

    def write_holding_register(self, address: int, value: int) -> None:
        self.holding_registers[address] = int(value) & 0xFFFF
        self.tick()

    def close(self) -> None:
        return None

    def tick(self) -> None:
        now = _now_ms()
        inputs = self._inputs()
        state = self._state()
        previous_state = state

        if not inputs["ESTOP_OK_NC"]:
            self._fault(FaultCode.ESTOP)
        elif state == StateCode.FAULT:
            if self._rising("RESET_PB", inputs["RESET_PB"]) and self._reset_permitted(inputs):
                self._clear_fault()
                self._set_state(StateCode.IDLE)
        elif state == StateCode.IDLE:
            if inputs["AUTO_MODE"] and self._rising("CYCLE_START", inputs["CYCLE_START"]) and self._reset_permitted(inputs):
                self._set_state(StateCode.READY)
        elif state == StateCode.READY:
            if not inputs["AUTO_MODE"]:
                self._set_state(StateCode.IDLE)
            elif self._rising("UNIT_AT_INSPECTION", inputs["UNIT_AT_INSPECTION"]):
                self.current_serial = inputs["UNIT_SERIAL"]
                self.current_fail_reason = 0
                self.cycle_start_ms = now
                self.vision_stable_since_ms = None
                self.vision_unstable_since_ms = None
                self.vision_last = inputs["VISION_PASS"]
                self._set_state(StateCode.INSPECTING)
        elif state == StateCode.INSPECTING:
            self._tick_inspecting(now, inputs)
        elif state == StateCode.PASS_RELEASE:
            if now - self.state_entered_ms >= PASS_RELEASE_MS and inputs["DOWNSTREAM_CLEAR"]:
                self._complete_unit(ResultCode.PASS, 0, now)
                self._set_state(StateCode.READY)
        elif state == StateCode.REJECT_EXTEND:
            if not inputs["GUARD_CLOSED_NC"]:
                self._fault(FaultCode.GUARD)
            elif inputs["PUSHER_EXTENDED"]:
                if self.reject_settle_since_ms is None:
                    self.reject_settle_since_ms = now
                elif now - self.reject_settle_since_ms >= REJECT_SETTLE_MS:
                    self.reject_settle_since_ms = None
                    self._set_state(StateCode.REJECT_RETRACT)
            elif now - self.state_entered_ms >= PUSHER_EXTEND_TIMEOUT_MS:
                self._fault(FaultCode.EXTEND_TIMEOUT)
        elif state == StateCode.REJECT_RETRACT:
            if inputs["PUSHER_RETRACTED"]:
                self._complete_unit(ResultCode.FAIL, self.current_fail_reason, now)
                self._set_state(StateCode.READY)
            elif now - self.state_entered_ms >= PUSHER_RETRACT_TIMEOUT_MS:
                self._fault(FaultCode.RETRACT_TIMEOUT)

        self._tick_unit_stuck(now, inputs)
        self._remember_edges(inputs)
        self._update_outputs()
        if previous_state != self._state():
            self._update_outputs()

    def _tick_inspecting(self, now: int, inputs: dict[str, bool | int]) -> None:
        if not inputs["VISION_RESULT_VALID"]:
            self.vision_stable_since_ms = None
            self.vision_unstable_since_ms = None
            self.vision_last = bool(inputs["VISION_PASS"])
            return

        current_pass = bool(inputs["VISION_PASS"])
        if current_pass != self.vision_last:
            self.vision_last = current_pass
            self.vision_stable_since_ms = now
            if self.vision_unstable_since_ms is None:
                self.vision_unstable_since_ms = now
        elif self.vision_stable_since_ms is None:
            self.vision_stable_since_ms = now

        if self.vision_unstable_since_ms is not None and now - self.vision_unstable_since_ms >= VISION_UNSTABLE_MS:
            self._fault(FaultCode.VISION_UNSTABLE)
            return

        if self.vision_stable_since_ms is not None and now - self.vision_stable_since_ms >= VISION_STABLE_MS:
            if current_pass:
                self._set_state(StateCode.PASS_RELEASE)
            else:
                self.current_fail_reason = int(inputs["FAIL_REASON"])
                self._set_state(StateCode.REJECT_EXTEND)

    def _tick_unit_stuck(self, now: int, inputs: dict[str, bool | int]) -> None:
        if self.unit_release_monitor_since_ms is None:
            return
        if not inputs["UNIT_AT_INSPECTION"]:
            self.unit_release_monitor_since_ms = None
        elif now - self.unit_release_monitor_since_ms >= UNIT_STUCK_HIGH_MS:
            self._fault(FaultCode.UNIT_STUCK)

    def _complete_unit(self, result: ResultCode, fail_reason: int, now: int) -> None:
        self.holding_registers[HOLDING_REGISTERS["TOTAL_UNITS"].address] += 1
        if result == ResultCode.FAIL:
            self.holding_registers[HOLDING_REGISTERS["TOTAL_REJECTS"].address] += 1
        self.holding_registers[HOLDING_REGISTERS["LAST_CYCLE_TIME_MS"].address] = max(0, now - self.cycle_start_ms)
        self.holding_registers[HOLDING_REGISTERS["LAST_SERIAL"].address] = self.current_serial
        self.holding_registers[HOLDING_REGISTERS["LAST_RESULT"].address] = int(result)
        self.holding_registers[HOLDING_REGISTERS["LAST_FAIL_REASON"].address] = int(fail_reason)
        self.unit_release_monitor_since_ms = now

    def _inputs(self) -> dict[str, bool | int]:
        return {
            "UNIT_AT_INSPECTION": self.coils[COILS["SIM_UNIT_AT_INSPECTION"].address],
            "UNIT_AT_REJECT": self.coils[COILS["SIM_UNIT_AT_REJECT"].address],
            "VISION_PASS": self.coils[COILS["SIM_VISION_PASS"].address],
            "VISION_RESULT_VALID": self.coils[COILS["SIM_VISION_RESULT_VALID"].address],
            "ESTOP_OK_NC": self.coils[COILS["SIM_ESTOP_OK_NC"].address],
            "GUARD_CLOSED_NC": self.coils[COILS["SIM_GUARD_CLOSED_NC"].address],
            "AUTO_MODE": self.coils[COILS["SIM_AUTO_MODE"].address],
            "CYCLE_START": self.coils[COILS["SIM_CYCLE_START"].address],
            "RESET_PB": self.coils[COILS["SIM_RESET_PB"].address],
            "PUSHER_EXTENDED": self.coils[COILS["SIM_PUSHER_EXTENDED"].address],
            "PUSHER_RETRACTED": self.coils[COILS["SIM_PUSHER_RETRACTED"].address],
            "DOWNSTREAM_CLEAR": self.coils[COILS["SIM_DOWNSTREAM_CLEAR"].address],
            "UNIT_SERIAL": self.holding_registers[HOLDING_REGISTERS["SIM_UNIT_SERIAL_IN"].address],
            "FAIL_REASON": self.holding_registers[HOLDING_REGISTERS["SIM_FAIL_REASON_IN"].address],
        }

    def _update_outputs(self) -> None:
        state = self._state()
        inputs = self._inputs()
        fault = state == StateCode.FAULT
        all_safe = bool(inputs["ESTOP_OK_NC"] and inputs["GUARD_CLOSED_NC"])
        extend = state == StateCode.REJECT_EXTEND and all_safe and not inputs["PUSHER_EXTENDED"]
        retract = state == StateCode.REJECT_RETRACT and inputs["ESTOP_OK_NC"] and not inputs["PUSHER_RETRACTED"]

        if extend and retract:
            self._fault(FaultCode.OUTPUT_CONFLICT)
            extend = False
            retract = False

        self._set_output("CONVEYOR_RUN", not fault and all_safe and state in {StateCode.READY, StateCode.PASS_RELEASE})
        self._set_output("PUSHER_EXTEND", not fault and extend and not retract)
        self._set_output("PUSHER_RETRACT", not fault and retract and not extend)
        self._set_output(
            "PASS_LAMP",
            not fault and self.holding_registers[HOLDING_REGISTERS["LAST_RESULT"].address] == ResultCode.PASS,
        )
        self._set_output(
            "FAIL_LAMP",
            not fault and self.holding_registers[HOLDING_REGISTERS["LAST_RESULT"].address] == ResultCode.FAIL,
        )
        self._set_output("FAULT_LAMP", fault)
        self._set_output("STATION_READY", not fault and all_safe and state == StateCode.READY and inputs["AUTO_MODE"])

    def _set_output(self, name: str, value: bool) -> None:
        self.coils[COILS[name].address] = value

    def _set_state(self, state: StateCode) -> None:
        self.holding_registers[HOLDING_REGISTERS["STATE_CODE"].address] = int(state)
        self.state_entered_ms = _now_ms()

    def _state(self) -> StateCode:
        return StateCode(self.holding_registers[HOLDING_REGISTERS["STATE_CODE"].address])

    def _fault(self, fault_code: FaultCode) -> None:
        self.fault_latched = True
        self.fault_code = fault_code
        self.holding_registers[HOLDING_REGISTERS["FAULT_CODE"].address] = int(fault_code)
        self._set_state(StateCode.FAULT)

    def _clear_fault(self) -> None:
        self.fault_latched = False
        self.fault_code = FaultCode.NONE
        self.holding_registers[HOLDING_REGISTERS["FAULT_CODE"].address] = int(FaultCode.NONE)

    def _reset_permitted(self, inputs: dict[str, bool | int]) -> bool:
        return bool(
            inputs["ESTOP_OK_NC"]
            and inputs["GUARD_CLOSED_NC"]
            and inputs["AUTO_MODE"]
            and inputs["PUSHER_RETRACTED"]
        )

    def _rising(self, name: str, value: bool | int) -> bool:
        last_key = f"_last_{name}"
        return bool(value) and not bool(getattr(self, last_key, False))

    def _remember_edges(self, inputs: dict[str, bool | int]) -> None:
        for name in ("CYCLE_START", "RESET_PB", "UNIT_AT_INSPECTION"):
            setattr(self, f"_last_{name}", bool(inputs[name]))

    def _write_defaults(self) -> None:
        self.coils[COILS["SIM_MODE"].address] = True
        self.coils[COILS["SIM_ESTOP_OK_NC"].address] = True
        self.coils[COILS["SIM_GUARD_CLOSED_NC"].address] = True
        self.coils[COILS["SIM_PUSHER_RETRACTED"].address] = True
        self.coils[COILS["SIM_DOWNSTREAM_CLEAR"].address] = True


def _now_ms() -> int:
    return int(time.monotonic() * 1000)
