import numpy as np

from anomaly import FEATURE_NAMES, fit, score_one, synthetic_nominal


def test_nominal_score_bas_dos_score_haut():
    model, normalizer = fit(synthetic_nominal())

    nominal = {"canary_success_ratio": 1.0, "canary_up": 1.0, "latency_p95": 0.05,
               "throughput": 0.25, "errors_5xx": 0.0, "request_rate": 1.0}
    # DoS : canari en échec, latence et erreurs qui explosent, débit qui s'effondre
    dos = {"canary_success_ratio": 0.2, "canary_up": 0.0, "latency_p95": 3.0,
           "throughput": 0.0, "errors_5xx": 5.0, "request_rate": 40.0}

    assert score_one(model, normalizer, nominal) < 0.5
    assert score_one(model, normalizer, dos) > 0.7


def test_la_grande_majorite_du_nominal_est_sous_le_seuil():
    data = synthetic_nominal(n=2000, seed=1)
    model, normalizer = fit(data)
    scores = np.array([score_one(model, normalizer, dict(zip(FEATURE_NAMES, row))) for row in data])
    # Moins de 5 % de faux positifs instantanés (le service exige en plus 3 relevés consécutifs)
    assert (scores >= 0.7).mean() < 0.05


def test_score_borne_entre_0_et_1():
    model, normalizer = fit(synthetic_nominal())
    extreme = {name: 1e6 for name in FEATURE_NAMES}
    assert 0.0 <= score_one(model, normalizer, extreme) <= 1.0


def test_modele_reproductible():
    m1, n1 = fit(synthetic_nominal(seed=7))
    m2, n2 = fit(synthetic_nominal(seed=7))
    point = {"canary_success_ratio": 0.5, "canary_up": 1.0, "latency_p95": 0.5,
             "throughput": 0.1, "errors_5xx": 1.0, "request_rate": 10.0}
    assert score_one(m1, n1, point) == score_one(m2, n2, point)
