from __future__ import annotations

import time
from dataclasses import dataclass
from enum import IntEnum
from typing import Mapping, Protocol


class StateCode(IntEnum):
    IDLE = 0
    READY = 10
    INSPECTING = 20
    PASS_RELEASE = 30
    REJECT_EXTEND = 40
    REJECT_RETRACT = 50
    FAULT = 90


class ResultCode(IntEnum):
    NONE = 0
    PASS = 1
    FAIL = 2


class FaultCode(IntEnum):
    NONE = 0
    ESTOP = 100
    GUARD = 110
    EXTEND_TIMEOUT = 120
    RETRACT_TIMEOUT = 130
    UNIT_STUCK = 140
    VISION_UNSTABLE = 150
    OUTPUT_CONFLICT = 160


@dataclass(frozen=True)
class Signal:
    name: str
    address: int
    description: str


COILS: dict[str, Signal] = {
    "CONVEYOR_RUN": Signal("CONVEYOR_RUN", 0, "Conveyor motor commanded on"),
    "PUSHER_EXTEND": Signal("PUSHER_EXTEND", 1, "Pusher extend solenoid"),
    "PUSHER_RETRACT": Signal("PUSHER_RETRACT", 2, "Pusher retract solenoid"),
    "PASS_LAMP": Signal("PASS_LAMP", 3, "Pass indicator lamp"),
    "FAIL_LAMP": Signal("FAIL_LAMP", 4, "Fail indicator lamp"),
    "FAULT_LAMP": Signal("FAULT_LAMP", 5, "Fault indicator lamp"),
    "STATION_READY": Signal("STATION_READY", 6, "Ready indicator"),
    "SIM_MODE": Signal("SIM_MODE", 16, "Use simulation input layer"),
    "SIM_UNIT_AT_INSPECTION": Signal("SIM_UNIT_AT_INSPECTION", 17, "Simulated inspection photoeye"),
    "SIM_UNIT_AT_REJECT": Signal("SIM_UNIT_AT_REJECT", 18, "Simulated reject photoeye"),
    "SIM_VISION_PASS": Signal("SIM_VISION_PASS", 19, "Simulated pass/fail result"),
    "SIM_VISION_RESULT_VALID": Signal("SIM_VISION_RESULT_VALID", 20, "Simulated vision result valid"),
    "SIM_ESTOP_OK_NC": Signal("SIM_ESTOP_OK_NC", 21, "Simulated E-stop healthy-high input"),
    "SIM_GUARD_CLOSED_NC": Signal("SIM_GUARD_CLOSED_NC", 22, "Simulated guard healthy-high input"),
    "SIM_AUTO_MODE": Signal("SIM_AUTO_MODE", 23, "Simulated automatic mode selector"),
    "SIM_CYCLE_START": Signal("SIM_CYCLE_START", 24, "Simulated start button"),
    "SIM_RESET_PB": Signal("SIM_RESET_PB", 25, "Simulated reset button"),
    "SIM_PUSHER_EXTENDED": Signal("SIM_PUSHER_EXTENDED", 26, "Simulated pusher extended confirmation"),
    "SIM_PUSHER_RETRACTED": Signal("SIM_PUSHER_RETRACTED", 27, "Simulated pusher retracted confirmation"),
    "SIM_DOWNSTREAM_CLEAR": Signal("SIM_DOWNSTREAM_CLEAR", 28, "Simulated downstream clear permissive"),
}


HOLDING_REGISTERS: dict[str, Signal] = {
    "STATE_CODE": Signal("STATE_CODE", 0, "Current state code"),
    "TOTAL_UNITS": Signal("TOTAL_UNITS", 1, "Completed unit count"),
    "TOTAL_REJECTS": Signal("TOTAL_REJECTS", 2, "Rejected unit count"),
    "LAST_CYCLE_TIME_MS": Signal("LAST_CYCLE_TIME_MS", 3, "Last cycle time in milliseconds"),
    "FAULT_CODE": Signal("FAULT_CODE", 4, "Latched fault code"),
    "LAST_SERIAL": Signal("LAST_SERIAL", 5, "Last completed serial"),
    "LAST_RESULT": Signal("LAST_RESULT", 6, "Last completed result"),
    "LAST_FAIL_REASON": Signal("LAST_FAIL_REASON", 7, "Last completed failure reason"),
    "SCENARIO_STEP": Signal("SCENARIO_STEP", 8, "Diagnostic scenario marker"),
    "SIM_UNIT_SERIAL_IN": Signal("SIM_UNIT_SERIAL_IN", 20, "Simulated unit serial input"),
    "SIM_FAIL_REASON_IN": Signal("SIM_FAIL_REASON_IN", 21, "Simulated failure reason input"),
}


OUTPUT_COILS = frozenset(
    {
        "CONVEYOR_RUN",
        "PUSHER_EXTEND",
        "PUSHER_RETRACT",
        "PASS_LAMP",
        "FAIL_LAMP",
        "FAULT_LAMP",
        "STATION_READY",
    }
)


SIM_INPUT_COILS = frozenset(name for name in COILS if name.startswith("SIM_"))
SIM_INPUT_REGISTERS = frozenset({"SIM_UNIT_SERIAL_IN", "SIM_FAIL_REASON_IN"})


class Backend(Protocol):
    def read_coil(self, address: int) -> bool: ...

    def write_coil(self, address: int, value: bool) -> None: ...

    def read_holding_register(self, address: int) -> int: ...

    def write_holding_register(self, address: int, value: int) -> None: ...

    def close(self) -> None: ...


class StationClient:
    def __init__(self, backend: Backend):
        self.backend = backend

    def close(self) -> None:
        self.backend.close()

    def read_coil(self, name: str) -> bool:
        return self.backend.read_coil(_address(COILS, name))

    def write_coil(self, name: str, value: bool) -> None:
        if name not in SIM_INPUT_COILS:
            raise ValueError(f"{name} is not a writable simulation input coil")
        self.backend.write_coil(_address(COILS, name), value)

    def read_register(self, name: str) -> int:
        return self.backend.read_holding_register(_address(HOLDING_REGISTERS, name))

    def write_register(self, name: str, value: int) -> None:
        if name not in SIM_INPUT_REGISTERS and name != "SCENARIO_STEP":
            raise ValueError(f"{name} is not a writable simulation input register")
        self.backend.write_holding_register(_address(HOLDING_REGISTERS, name), value)

    def pulse(self, name: str, duration_s: float = 0.05) -> None:
        self.write_coil(name, True)
        time.sleep(duration_s)
        self.write_coil(name, False)

    def initialize_simulation_inputs(self) -> None:
        safe_defaults = {
            "SIM_MODE": True,
            "SIM_UNIT_AT_INSPECTION": False,
            "SIM_UNIT_AT_REJECT": False,
            "SIM_VISION_PASS": False,
            "SIM_VISION_RESULT_VALID": False,
            "SIM_ESTOP_OK_NC": True,
            "SIM_GUARD_CLOSED_NC": True,
            "SIM_AUTO_MODE": True,
            "SIM_CYCLE_START": False,
            "SIM_RESET_PB": False,
            "SIM_PUSHER_EXTENDED": False,
            "SIM_PUSHER_RETRACTED": True,
            "SIM_DOWNSTREAM_CLEAR": True,
        }
        for name, value in safe_defaults.items():
            self.write_coil(name, value)
        self.write_register("SIM_UNIT_SERIAL_IN", 0)
        self.write_register("SIM_FAIL_REASON_IN", 0)
        self.write_register("SCENARIO_STEP", 0)

    def snapshot(self) -> dict[str, bool | int]:
        snap: dict[str, bool | int] = {}
        for name in COILS:
            snap[name] = self.read_coil(name)
        for name in HOLDING_REGISTERS:
            snap[name] = self.read_register(name)
        return snap


class PymodbusBackend:
    def __init__(self, host: str = "localhost", port: int = 502, unit_id: int = 1):
        try:
            from pymodbus.client import ModbusTcpClient
        except ImportError as exc:
            raise RuntimeError("pymodbus is required for the OpenPLC backend") from exc

        self.unit_id = unit_id
        self.client = ModbusTcpClient(host=host, port=port)
        if not self.client.connect():
            raise ConnectionError(f"Could not connect to Modbus TCP at {host}:{port}")

    def close(self) -> None:
        self.client.close()

    def read_coil(self, address: int) -> bool:
        result = self._call(self.client.read_coils, address=address, count=1)
        self._raise_on_error(result, f"read coil {address}")
        return bool(result.bits[0])

    def write_coil(self, address: int, value: bool) -> None:
        result = self._call(self.client.write_coil, address=address, value=value)
        self._raise_on_error(result, f"write coil {address}")

    def read_holding_register(self, address: int) -> int:
        result = self._call(self.client.read_holding_registers, address=address, count=1)
        self._raise_on_error(result, f"read holding register {address}")
        return int(result.registers[0])

    def write_holding_register(self, address: int, value: int) -> None:
        result = self._call(self.client.write_register, address=address, value=value)
        self._raise_on_error(result, f"write holding register {address}")

    def _call(self, method, **kwargs):
        try:
            return method(**kwargs, device_id=self.unit_id)
        except TypeError:
            return method(**kwargs, slave=self.unit_id)

    @staticmethod
    def _raise_on_error(result: object, operation: str) -> None:
        if hasattr(result, "isError") and result.isError():
            raise IOError(f"Modbus {operation} failed: {result}")


def _address(signals: Mapping[str, Signal], name: str) -> int:
    try:
        return signals[name].address
    except KeyError as exc:
        raise KeyError(f"Unknown signal {name}") from exc
