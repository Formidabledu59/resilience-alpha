"""Collecte des preuves d'un incident dans Prometheus (métriques) et Loki (journaux du WAF).

Lecture seule. Chaque requête qui échoue renvoie None : un incident est toujours journalisé,
même si une source d'observabilité est indisponible (le champ "sources" le signale).
"""

import httpx

# Mêmes extractions que le dashboard Grafana "Frontal et sécurité"
WAF_ACCESS = '{service="waf"} |= "\\"client\\"" | json'
WAF_AUDIT_RULES = ('{service="waf"} |= "\\"transaction\\"" | json rule="transaction.messages[0].details.ruleId", '
                   'code="transaction.response.http_code" | code="403" | rule!=""')
AUTH_FAILURES = '{service="auth-service"} |= "POST /auth/token" |= " 401"'

P95 = "histogram_quantile(0.95, sum by (le) (rate(canary_latency_seconds_bucket[1m])))"
ERRORS_5XX = 'sum(rate(http_requests_total{status="5xx"}[1m])) or vector(0)'

MIN_WINDOW, MAX_WINDOW = 60, 3600


class Observer:
    def __init__(self, client: httpx.AsyncClient, prometheus_url: str, loki_url: str):
        self.client = client
        self.prometheus_url = prometheus_url.rstrip("/")
        self.loki_url = loki_url.rstrip("/")

    async def _query(self, url: str, promql: str) -> list | None:
        try:
            response = await self.client.get(url, params={"query": promql})
            response.raise_for_status()
            return response.json()["data"]["result"]
        except (httpx.HTTPError, KeyError, ValueError):
            return None

    async def prometheus(self, promql: str) -> list | None:
        return await self._query(f"{self.prometheus_url}/api/v1/query", promql)

    async def loki(self, logql: str) -> list | None:
        return await self._query(f"{self.loki_url}/loki/api/v1/query", logql)

    async def prometheus_value(self, promql: str) -> float | None:
        result = await self.prometheus(promql)
        if not result:
            return None
        try:
            value = float(result[0]["value"][1])
        except (KeyError, IndexError, ValueError):
            return None
        return None if value != value else value  # NaN (aucune donnée) -> None

    async def canary_state(self) -> tuple[float | None, float | None]:
        """(canary_up, canary_success_ratio) actuels, utilisés pour vérifier la reprise."""
        return await self.prometheus_value("canary_up"), await self.prometheus_value("canary_success_ratio")

    async def collect(self, window_seconds: float) -> dict:
        """Photographie de la plateforme sur la fenêtre [maintenant - window, maintenant]."""
        window = f"{int(min(max(window_seconds, MIN_WINDOW), MAX_WINDOW))}s"

        metrics = {
            "canary_up": await self.prometheus_value("canary_up"),
            "canary_success_ratio": await self.prometheus_value("canary_success_ratio"),
            "canary_success_min": await self.prometheus_value(f"min_over_time(canary_success_ratio[{window}])"),
            "latency_p95": await self.prometheus_value(P95),
            "latency_p95_peak": await self.prometheus_value(f"max_over_time(({P95})[{window}:15s])"),
            "errors_5xx_rate": await self.prometheus_value(ERRORS_5XX),
            "errors_5xx_peak": await self.prometheus_value(f"max_over_time(({ERRORS_5XX})[{window}:15s])"),
            "throughput": await self.prometheus_value("sum(rate(payment_transactions_total[1m]))"),
        }

        blocked = await self.loki(f'sum(count_over_time({WAF_ACCESS} | status="403" [{window}]))')
        limited = await self.loki(f'sum(count_over_time({WAF_ACCESS} | status="429" [{window}]))')
        rules = await self.loki(f"sum by (rule) (count_over_time({WAF_AUDIT_RULES} [{window}]))")
        clients = await self.loki(f'sum by (client) (count_over_time({WAF_ACCESS} | status=~"403|429" [{window}]))')
        talkers = await self.loki(f"sum by (client) (count_over_time({WAF_ACCESS} [{window}]))")  # toutes requêtes
        auth = await self.loki(f"sum(count_over_time({AUTH_FAILURES} [{window}]))")

        loki_ok = any(r is not None for r in (blocked, limited, rules, clients, talkers, auth))
        return {
            "window_seconds": int(window[:-1]),
            "sources": {"prometheus": any(v is not None for v in metrics.values()), "loki": loki_ok},
            "metrics": metrics,
            "waf": {
                "blocked_403": _total(blocked),
                "rate_limited_429": _total(limited),
                "rules": _by_label(rules, "rule"),
                "clients": [{"ip": c["client"], "count": c["count"]} for c in _by_label(clients, "client")[:5]],
                "top_clients": [{"ip": c["client"], "count": c["count"]} for c in _by_label(talkers, "client")[:5]],
            },
            "auth_failures": _total(auth),
        }


def _total(result: list | None) -> int | None:
    if result is None:
        return None
    return sum(int(float(item["value"][1])) for item in result)


def _by_label(result: list | None, label: str) -> list[dict]:
    """[{label: valeur, count: n}] trié du plus fréquent au moins fréquent."""
    items = [{label: item["metric"].get(label, "?"), "count": int(float(item["value"][1]))} for item in result or []]
    return sorted((i for i in items if i["count"] > 0), key=lambda i: i["count"], reverse=True)
