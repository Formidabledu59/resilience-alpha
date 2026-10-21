import asyncio
import hashlib
import hmac

import httpx
import pytest

import main
from main import Detector, sign
from model_store import load_or_fallback

SECRET = "secret-de-test"

NOMINAL = {"canary_success_ratio": 1.0, "canary_up": 1.0, "latency_p95": 0.05,
           "throughput": 0.25, "errors_5xx": 0.0, "request_rate": 1.0}
DOS = {"canary_success_ratio": 0.1, "canary_up": 0.0, "latency_p95": 4.0,
       "throughput": 0.0, "errors_5xx": 8.0, "request_rate": 50.0}


def make_detector(handler, features):
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    detector = Detector(load_or_fallback("/inexistant/model.joblib"), client, SECRET)

    async def fake_read(_client, _url):
        return features["value"], features["ok"]

    main.read_features = fake_read
    return detector, client


def test_signature_hmac_conforme_au_moteur():
    body = b'{"score":0.9}'
    headers = sign(SECRET, body, now=1000)
    expected = "sha256=" + hmac.new(SECRET.encode(), b"1000." + body, hashlib.sha256).hexdigest()
    assert headers["X-Resilience-Timestamp"] == "1000"
    assert headers["X-Resilience-Signature"] == expected


def test_alerte_apres_trois_releves_consecutifs():
    sent = []

    def handler(request):
        sent.append(request)
        return httpx.Response(202, json={"incident": "inc-2026-10-21-001"})

    features = {"value": DOS, "ok": True}

    async def scenario():
        detector, client = make_detector(handler, features)
        async with client:
            results = [await detector.tick(now=100 + i) for i in range(3)]
        return results

    results = asyncio.run(scenario())
    assert [r["alert"] for r in results] == [False, False, True]  # il faut 3 relevés au-dessus du seuil
    assert all(r["score"] > 0.7 for r in results)
    assert len(sent) == 1
    # Signature vérifiable côté moteur
    request = sent[0]
    timestamp = request.headers["X-Resilience-Timestamp"]
    expected = "sha256=" + hmac.new(SECRET.encode(), timestamp.encode() + b"." + request.content, hashlib.sha256).hexdigest()
    assert request.headers["X-Resilience-Signature"] == expected


def test_pas_d_alerte_en_trafic_nominal():
    def handler(request):
        raise AssertionError("aucune alerte ne doit partir en trafic nominal")

    async def scenario():
        detector, client = make_detector(handler, {"value": NOMINAL, "ok": True})
        async with client:
            return [await detector.tick(now=100 + i) for i in range(5)]

    results = asyncio.run(scenario())
    assert all(r["alert"] is False for r in results)
    assert all(r["score"] < 0.7 for r in results)


def test_une_sequence_breve_ne_declenche_pas():
    def handler(request):
        raise AssertionError("deux relevés ne suffisent pas")

    seq = [DOS, DOS, NOMINAL, DOS]  # jamais 3 d'affilée
    state = {"i": 0}

    async def scenario():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        detector = Detector(load_or_fallback("/inexistant"), client, SECRET)

        async def fake_read(_c, _u):
            value = seq[state["i"]]
            state["i"] += 1
            return value, True

        main.read_features = fake_read
        async with client:
            return [await detector.tick(now=100 + i) for i in range(len(seq))]

    assert all(r["alert"] is False for r in asyncio.run(scenario()))


def test_prometheus_injoignable_ne_plante_pas():
    def handler(request):
        raise AssertionError("pas d'alerte si Prometheus est muet")

    async def scenario():
        detector, client = make_detector(handler, {"value": {}, "ok": False})
        async with client:
            return await detector.tick(now=100)

    result = asyncio.run(scenario())
    assert result == {"prometheus_ok": False, "score": None, "alert": False}
