"""Stateful property test: station model vs the written spec.

Oracle source: docs/state_machine.md and plc/io_map.md, not sim/io_simulator.py.
Runs on a fake clock so hundreds of input sequences finish in seconds.
Set STATION_EXAMPLES to change the number of generated sequences.
"""
import os
from collections import Counter
from unittest import mock

import pytest
from hypothesis import settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, precondition, rule

from harness.modbus_client import COILS, HOLDING_REGISTERS, SIM_INPUT_COILS, StateCode, StationClient
from sim import io_simulator
from sim.io_simulator import InMemoryBackend

S = StateCode
ALLOWED = {
    S.IDLE: {S.IDLE, S.READY, S.FAULT},
    S.READY: {S.READY, S.IDLE, S.INSPECTING, S.FAULT},
    S.INSPECTING: {S.INSPECTING, S.PASS_RELEASE, S.REJECT_EXTEND, S.FAULT},
    S.PASS_RELEASE: {S.PASS_RELEASE, S.READY, S.FAULT},
    S.REJECT_EXTEND: {S.REJECT_EXTEND, S.REJECT_RETRACT, S.FAULT},
    S.REJECT_RETRACT: {S.REJECT_RETRACT, S.READY, S.FAULT},
    S.FAULT: {S.FAULT, S.IDLE},
}
FLIP_COILS = sorted(SIM_INPUT_COILS - {"SIM_MODE"})
SAFETY_COILS = ["SIM_ESTOP_OK_NC", "SIM_GUARD_CLOSED_NC"]
BENIGN_COILS = [c for c in FLIP_COILS if c not in SAFETY_COILS]
COVERAGE: Counter = Counter()


class FakeClock:
    def __init__(self) -> None:
        self.ms = 1_000_000

    def __call__(self) -> int:
        return self.ms


class StationMachine(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        self.clock = FakeClock()
        self._patch = mock.patch.object(io_simulator, "_now_ms", self.clock)
        self._patch.start()
        self.backend = InMemoryBackend()
        StationClient(self.backend).initialize_simulation_inputs()
        self.prev = self.observe()
        self.state_entered = self.clock.ms
        self.state_entered_prev = self.state_entered
        self.arrival_serial = 0
        self.latched_reason = 0

    def teardown(self) -> None:
        self._patch.stop()

    def coil(self, name: str) -> bool:
        return bool(self.backend.coils[COILS[name].address])

    def reg(self, name: str) -> int:
        return int(self.backend.holding_registers[HOLDING_REGISTERS[name].address])

    def observe(self) -> dict:
        """One explicit tick, then non-ticking reads, so the snapshot is atomic (the model ticks on every access)."""
        self.backend.tick()
        obs = {"state": S(self.reg("STATE_CODE"))}
        for name in ("FAULT_CODE", "TOTAL_UNITS", "TOTAL_REJECTS", "LAST_SERIAL", "LAST_RESULT", "LAST_FAIL_REASON"):
            obs[name] = self.reg(name)
        for name in ("CONVEYOR_RUN", "PUSHER_EXTEND", "PUSHER_RETRACT", "PASS_LAMP", "FAIL_LAMP", "FAULT_LAMP", "STATION_READY"):
            obs[name] = self.coil(name)
        for name in FLIP_COILS:
            obs[name] = self.coil(name)
        obs["SERIAL_IN"] = self.reg("SIM_UNIT_SERIAL_IN")
        obs["REASON_IN"] = self.reg("SIM_FAIL_REASON_IN")
        return obs

    def write(self, name: str, value: bool) -> None:
        before = self.coil(name)
        self.backend.coils[COILS[name].address] = bool(value)
        self.check(reset_edge=(name == "SIM_RESET_PB" and value and not before))

    def write_reg(self, name: str, value: int) -> None:
        self.backend.holding_registers[HOLDING_REGISTERS[name].address] = value & 0xFFFF
        self.check()

    def check(self, reset_edge: bool = False) -> None:
        p, o = self.prev, self.observe()
        self.state_entered_prev = self.state_entered
        if o["state"] != p["state"]:
            self.state_entered = self.clock.ms
        COVERAGE[f"state={o['state'].name}"] += 1
        COVERAGE[f"edge={p['state'].name}->{o['state'].name}"] += 1
        if o["FAULT_CODE"]:
            COVERAGE[f"fault={o['FAULT_CODE']}"] += 1
        safe = o["SIM_ESTOP_OK_NC"] and o["SIM_GUARD_CLOSED_NC"]
        s, elapsed = o["state"], self.clock.ms - self.state_entered

        assert s in ALLOWED[p["state"]], f"illegal transition {p['state'].name}->{s.name}"
        if p["state"] == S.FAULT and s == S.IDLE:
            permissive = safe and o["SIM_AUTO_MODE"] and o["SIM_PUSHER_RETRACTED"]
            assert reset_edge and permissive, "left FAULT without a reset rising edge and healthy permissives"

        if not o["SIM_ESTOP_OK_NC"]:
            assert s == S.FAULT and o["FAULT_LAMP"], "E-stop open but not faulted"
            assert not (o["CONVEYOR_RUN"] or o["PUSHER_EXTEND"] or o["PUSHER_RETRACT"]), "motion output on with E-stop open"
            assert o["FAULT_CODE"] == 100, f"E-stop open but FAULT_CODE={o['FAULT_CODE']} (spec: 100)"
        assert (o["FAULT_CODE"] != 0) == (s == S.FAULT) == o["FAULT_LAMP"], "fault code/state/lamp disagree"
        if p["state"] == S.REJECT_EXTEND and not o["SIM_GUARD_CLOSED_NC"] and o["SIM_ESTOP_OK_NC"]:
            assert s == S.FAULT and o["FAULT_CODE"] == 110, f"guard opened during extend -> {s.name}/{o['FAULT_CODE']}"

        if p["state"] != S.FAULT and s == S.FAULT and o["SIM_ESTOP_OK_NC"]:
            expected = {S.INSPECTING: {150}, S.REJECT_RETRACT: {130}, S.REJECT_EXTEND: {110, 120}}.get(p["state"])
            if expected:
                assert o["FAULT_CODE"] in expected, f"{p['state'].name}->FAULT with code {o['FAULT_CODE']}, spec allows {sorted(expected)}"
        if p["state"] == S.PASS_RELEASE and s == S.READY:
            assert o["SIM_DOWNSTREAM_CLEAR"], "left PASS_RELEASE with DOWNSTREAM_CLEAR false"
            assert self.clock.ms - self.state_entered_prev >= 500, "left PASS_RELEASE before PASS_RELEASE_MS"
        assert not (o["PUSHER_EXTEND"] and o["PUSHER_RETRACT"]), "extend and retract both on"
        if s == S.FAULT:
            assert not (o["CONVEYOR_RUN"] or o["PUSHER_EXTEND"] or o["PUSHER_RETRACT"]), "motion output on in FAULT"
        if o["CONVEYOR_RUN"]:
            assert s in (S.READY, S.PASS_RELEASE), f"conveyor on in {s.name}"
            assert safe, "conveyor on with E-stop/guard unhealthy"
            assert s == S.READY or o["SIM_DOWNSTREAM_CLEAR"], "conveyor on in PASS_RELEASE with DOWNSTREAM_CLEAR false"
        if o["PUSHER_EXTEND"]:
            assert s == S.REJECT_EXTEND and safe, "extend energized outside REJECT_EXTEND or unsafe"
        if o["PUSHER_RETRACT"]:
            assert s == S.REJECT_RETRACT and o["SIM_ESTOP_OK_NC"], "retract energized outside REJECT_RETRACT or unsafe"
        assert o["STATION_READY"] == (s == S.READY and safe and o["SIM_AUTO_MODE"]), "STATION_READY disagrees with spec"
        assert not (o["PASS_LAMP"] and o["FAIL_LAMP"]), "both result lamps on"
        if o["PASS_LAMP"]:
            assert o["LAST_RESULT"] == 1 and s != S.FAULT
        if o["FAIL_LAMP"]:
            assert o["LAST_RESULT"] == 2 and s != S.FAULT

        if s == S.REJECT_EXTEND and safe and not o["SIM_PUSHER_EXTENDED"]:
            assert elapsed < 1500, "extend timeout overdue"
        if s == S.REJECT_RETRACT and o["SIM_ESTOP_OK_NC"] and not o["SIM_PUSHER_RETRACTED"]:
            assert elapsed < 1500, "retract timeout overdue"

        if p["state"] == S.READY and s == S.INSPECTING:
            self.arrival_serial = o["SERIAL_IN"]
        if p["state"] == S.INSPECTING and s == S.REJECT_EXTEND:
            self.latched_reason = o["REASON_IN"]
        pass_done = p["state"] == S.PASS_RELEASE and s == S.READY
        fail_done = p["state"] == S.REJECT_RETRACT and s == S.READY
        d_units, d_rej = o["TOTAL_UNITS"] - p["TOTAL_UNITS"], o["TOTAL_REJECTS"] - p["TOTAL_REJECTS"]
        assert d_units == (1 if (pass_done or fail_done) else 0), f"TOTAL_UNITS delta {d_units} on {p['state'].name}->{s.name}"
        assert d_rej == (1 if fail_done else 0), f"TOTAL_REJECTS delta {d_rej} on {p['state'].name}->{s.name}"
        if pass_done or fail_done:
            assert o["LAST_SERIAL"] == self.arrival_serial, "LAST_SERIAL is not the serial present at arrival"
            assert o["LAST_RESULT"] == (1 if pass_done else 2)
            assert o["LAST_FAIL_REASON"] == (0 if pass_done else self.latched_reason)
        self.prev = o

    @initialize(hostile=st.sampled_from([False, False, True]))
    def choose_mix(self, hostile):
        self.hostile = hostile

    @rule(name=st.sampled_from(BENIGN_COILS), value=st.booleans())
    def flip(self, name, value):
        self.write(name, value)

    @precondition(lambda self: getattr(self, "hostile", False))
    @rule(name=st.sampled_from(SAFETY_COILS), value=st.booleans())
    def flip_safety(self, name, value):
        self.write(name, value)

    @rule(passing=st.booleans(), serial=st.integers(0, 65535), reason=st.integers(0, 4), extend_first=st.booleans(), leave_unit=st.booleans())
    def full_cycle(self, passing, serial, reason, extend_first, leave_unit):
        self.write("SIM_AUTO_MODE", True)
        self.write("SIM_CYCLE_START", False)
        self.write("SIM_CYCLE_START", True)
        self.write_reg("SIM_UNIT_SERIAL_IN", serial)
        self.write_reg("SIM_FAIL_REASON_IN", reason)
        self.write("SIM_UNIT_AT_INSPECTION", False)
        self.write("SIM_UNIT_AT_INSPECTION", True)
        self.write("SIM_VISION_PASS", passing)
        self.write("SIM_VISION_RESULT_VALID", True)
        self.clock.ms += 300
        self.check()
        if not passing and extend_first:
            self.write("SIM_PUSHER_EXTENDED", True)
            self.write("SIM_PUSHER_RETRACTED", False)
            self.clock.ms += 300
            self.check()
            self.write("SIM_PUSHER_EXTENDED", False)
            self.write("SIM_PUSHER_RETRACTED", True)
        self.clock.ms += 600
        self.check()
        self.write("SIM_VISION_RESULT_VALID", False)
        if not leave_unit:
            self.write("SIM_UNIT_AT_INSPECTION", False)

    @rule(serial=st.integers(0, 65535))
    def set_serial(self, serial):
        self.write_reg("SIM_UNIT_SERIAL_IN", serial)

    @rule(reason=st.integers(0, 4))
    def set_reason(self, reason):
        self.write_reg("SIM_FAIL_REASON_IN", reason)

    @rule(dt=st.one_of(st.integers(1, 400), st.sampled_from([250, 260, 500, 1000, 1500, 1600, 3000, 3100])))
    def advance(self, dt):
        self.clock.ms += dt
        self.check()

    @rule()
    def press_start(self):
        self.write("SIM_AUTO_MODE", True)
        self.write("SIM_CYCLE_START", False)
        self.write("SIM_CYCLE_START", True)

    @rule()
    def press_reset(self):
        self.write("SIM_RESET_PB", False)
        self.write("SIM_RESET_PB", True)

    @rule()
    def unit_arrives(self):
        self.write("SIM_UNIT_AT_INSPECTION", False)
        self.write("SIM_UNIT_AT_INSPECTION", True)

    @rule(passing=st.booleans())
    def vision_result(self, passing):
        self.write("SIM_VISION_PASS", passing)
        self.write("SIM_VISION_RESULT_VALID", True)

    @rule(extended=st.booleans())
    def pusher_position(self, extended):
        self.write("SIM_PUSHER_EXTENDED", extended)
        self.write("SIM_PUSHER_RETRACTED", not extended)

    @invariant()
    def always(self):
        self.check()


StationMachine.TestCase.settings = settings(
    max_examples=int(os.environ.get("STATION_EXAMPLES", "1500")), stateful_step_count=60, deadline=None
)
TestStationStateful = StationMachine.TestCase


def _run_script(steps):
    m = StationMachine()
    try:
        for step in steps:
            step(m)
        return m
    finally:
        m.teardown()


def test_generator_reaches_every_state():
    """Distribution check: a fuzz run that never reaches a state proves nothing about it."""
    if not COVERAGE:
        pytest.skip("run together with TestStationStateful to collect coverage")
    missing = [s.name for s in StateCode if COVERAGE[f"state={s.name}"] == 0]
    assert not missing, f"generator never reached: {missing}"


def test_oracle_accepts_known_good_pass_and_reject_cycles():
    """Sanity: the oracle must not false-alarm on the documented happy paths."""
    m = _run_script([
        lambda m: m.press_start(),
        lambda m: m.set_serial(1001),
        lambda m: m.unit_arrives(),
        lambda m: m.vision_result(True),
        lambda m: m.advance(300),
        lambda m: m.advance(600),
        lambda m: m.write("SIM_UNIT_AT_INSPECTION", False),
        lambda m: m.set_reason(2),
        lambda m: m.unit_arrives(),
        lambda m: m.write("SIM_VISION_RESULT_VALID", False),
        lambda m: m.vision_result(False),
        lambda m: m.advance(300),
        lambda m: m.pusher_position(True),
        lambda m: m.advance(300),
        lambda m: m.pusher_position(False),
        lambda m: m.advance(10),
    ])
    assert (m.prev["state"], m.prev["TOTAL_UNITS"], m.prev["TOTAL_REJECTS"]) == (S.READY, 2, 1)


def test_regression_conveyor_stops_when_downstream_not_clear():
    """Found by the stateful test: CONVEYOR_RUN ignored DOWNSTREAM_CLEAR in PASS_RELEASE."""
    m = _run_script([
        lambda m: m.press_start(),
        lambda m: m.unit_arrives(),
        lambda m: m.vision_result(True),
        lambda m: m.write("SIM_DOWNSTREAM_CLEAR", False),
        lambda m: m.advance(300),
    ])
    assert m.prev["state"] == S.PASS_RELEASE
    assert m.prev["CONVEYOR_RUN"] is False


def test_regression_stuck_sensor_does_not_overwrite_estop_fault_code():
    """Found by the stateful test: the stuck-sensor timer overwrote an active E-stop fault code (100) with 140."""
    m = _run_script([
        lambda m: m.full_cycle(True, 1, 0, False, True),
        lambda m: m.write("SIM_ESTOP_OK_NC", False),
        lambda m: m.advance(3100),
    ])
    assert m.prev["state"] == S.FAULT
    assert m.prev["FAULT_CODE"] == 100
