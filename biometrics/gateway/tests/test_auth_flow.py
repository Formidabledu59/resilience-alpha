import auth_flow as af
from auth_flow import AuthFlow


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_recognized_then_password_ok():
    flow = AuthFlow()
    assert flow.start_identification("admin")["status"] == "camera_on"
    assert flow.on_recognition("admin", True)["status"] == "recognized"
    assert flow.led()["state"] == af.LED_GREEN_BLINK
    assert flow.submit_password("admin", True)["status"] == "granted"
    assert flow.led()["state"] == af.LED_GREEN_SOLID


def test_wrong_password_restarts_and_red_blink():
    flow = AuthFlow()
    flow.on_recognition("admin", True)
    assert flow.submit_password("admin", False)["status"] == "denied"
    assert flow.led()["state"] == af.LED_RED_BLINK
    # il faut repasser par la reconnaissance : le mot de passe seul est refusé
    assert flow.submit_password("admin", True)["status"] == "face_first"


def test_not_recognized_then_lockout_after_retry():
    clock = FakeClock()
    flow = AuthFlow(clock=clock)
    first = flow.on_recognition("admin", False)
    assert first["status"] == "not_recognized" and first["attempts_left"] == 1
    assert flow.led()["state"] == af.LED_RED_SOLID
    second = flow.on_recognition("admin", False)
    assert second["status"] == "locked" and second["retry_in"] == af.LOCKOUT_SECONDS
    assert flow.is_locked("admin")
    # bloqué : même un visage reconnu est refusé pendant le blocage
    assert flow.on_recognition("admin", True)["status"] == "locked"
    assert flow.start_identification("admin")["status"] == "locked"


def test_lockout_expires():
    clock = FakeClock()
    flow = AuthFlow(clock=clock)
    flow.on_recognition("admin", False)
    flow.on_recognition("admin", False)
    assert flow.is_locked("admin")
    clock.t += af.LOCKOUT_SECONDS + 1
    assert not flow.is_locked("admin")
    assert flow.start_identification("admin")["status"] == "camera_on"


def test_password_requires_prior_recognition():
    flow = AuthFlow()
    assert flow.submit_password("admin", True)["status"] == "face_first"


def test_led_seq_increments_on_change():
    flow = AuthFlow()
    s0 = flow.led()["seq"]
    flow.on_recognition("admin", True)
    assert flow.led()["seq"] == s0 + 1
    flow.submit_password("admin", True)
    assert flow.led()["seq"] == s0 + 2
    flow.reset_led()
    assert flow.led()["state"] == af.LED_OFF and flow.led()["seq"] == s0 + 3
