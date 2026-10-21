import pytest

from incidents import assess


class FakeObserver:
    """Remplace Prometheus et Loki : preuves fixes, état du canari programmable."""

    def __init__(self, evidence=None, canary=(1, 1.0)):
        self.evidence = evidence or sample_evidence()
        self.canary = canary
        self.windows = []

    async def collect(self, window_seconds):
        self.windows.append(window_seconds)
        return self.evidence

    async def canary_state(self):
        return self.canary


def sample_evidence(canary_min=1.0, blocked=42, limited=0):
    return {
        "window_seconds": 360,
        "sources": {"prometheus": True, "loki": True},
        "metrics": {
            "canary_up": 1, "canary_success_ratio": 1.0, "canary_success_min": canary_min,
            "latency_p95": 0.04, "latency_p95_peak": 1.2, "errors_5xx_rate": 0, "errors_5xx_peak": 0,
            "throughput": 0.2,
        },
        "waf": {
            "blocked_403": blocked,
            "rate_limited_429": limited,
            "rules": [{"rule": "942100", "count": 30}, {"rule": "942190", "count": 5}, {"rule": "941100", "count": 7}],
            "clients": [{"ip": "172.23.0.1", "count": blocked + limited}],
        },
        "auth_failures": 0,
    }


def make_incident(category="attaque_applicative", status="CLOSED", evidence=None):
    incident = {
        "id": "inc-2026-10-20-001", "status": status, "trigger": "Pic de 403", "source": "alertmanager",
        "category": category, "category_label": "Attaque applicative", "severity": "warning",
        "opened_at": "2026-10-20T14:00:05+00:00", "closed_at": "2026-10-20T14:01:20+00:00",
        "alerts": [{"name": "WafBlocagesModSecurity", "source": "alertmanager", "at": "2026-10-20T14:00:00+00:00",
                    "summary": "Pic de requêtes bloquées par le WAF"}],
        "evidence": {"opening": evidence or sample_evidence()},
        "steps": [{"at": "2026-10-20T14:01:20+00:00", "action": "Transaction de contrôle (POST /probe)",
                   "result": "COMPLETED, transaction n°12", "kind": "verification"}],
    }
    return assess(incident)


@pytest.fixture
def observer():
    return FakeObserver()
