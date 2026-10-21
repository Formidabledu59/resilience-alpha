"""Lecture des features dans Prometheus (lecture seule)."""

from __future__ import annotations

import httpx

from anomaly import QUERIES


async def scalar(client: httpx.AsyncClient, prometheus_url: str, promql: str) -> float | None:
    """Valeur instantanée d'une requête PromQL, ou None si indisponible / NaN."""
    try:
        response = await client.get(f"{prometheus_url}/api/v1/query", params={"query": promql})
        response.raise_for_status()
        result = response.json()["data"]["result"]
    except (httpx.HTTPError, KeyError, ValueError):
        return None
    if not result:
        return None
    try:
        value = float(result[0]["value"][1])
    except (KeyError, IndexError, ValueError):
        return None
    return None if value != value else value


async def read_features(client: httpx.AsyncClient, prometheus_url: str) -> tuple[dict, bool]:
    """Relevé {feature: valeur} et un booléen indiquant si Prometheus a répondu pour au moins une feature."""
    features, seen = {}, False
    for name, query in QUERIES.items():
        value = await scalar(client, prometheus_url, query)
        if value is not None:
            features[name] = value
            seen = True
    return features, seen
