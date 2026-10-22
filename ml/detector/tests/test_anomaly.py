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


NOMINAL = {"canary_success_ratio": 1.0, "canary_up": 1.0, "latency_p95": 0.05,
           "throughput": 0.25, "errors_5xx": 0.0, "request_rate": 1.0}


def test_canary_up_influence_le_score():
    # Régression : canary_up constant à l'entraînement était ignoré par l'Isolation Forest.
    model, normalizer = fit(synthetic_nominal())
    assert score_one(model, normalizer, {**NOMINAL, "canary_up": 0.0}) > score_one(model, normalizer, NOMINAL)


def test_degradation_realiste_declenche_l_alerte():
    # Ce que doit produire un DoS calibré : service dégradé sans être arrêté.
    model, normalizer = fit(synthetic_nominal())
    degrade = {"canary_success_ratio": 0.5, "canary_up": 1.0, "latency_p95": 2.0,
               "throughput": 0.1, "errors_5xx": 0.5, "request_rate": 11.0}
    assert score_one(model, normalizer, degrade) >= 0.7


def test_flood_absorbe_par_les_rate_limits_ne_declenche_pas():
    # Calibrage : si le WAF et le frontal absorbent tout (seul request_rate bouge), pas
    # d'incident. Le DoS doit dégrader réellement le service (docs/test-results/calibrage-attaque-dos.md).
    model, normalizer = fit(synthetic_nominal())
    assert score_one(model, normalizer, {**NOMINAL, "request_rate": 11.0}) < 0.7


def _nominal_reel(n=240, seed=3):
    """Nominal tel que collecté : canari toujours OK, aucune erreur, le reste varie peu."""
    rng = np.random.default_rng(seed)
    return np.column_stack([
        np.ones(n), np.ones(n),                      # canary_success_ratio, canary_up : constants
        rng.normal(0.02, 0.004, n).clip(0),          # latency_p95
        rng.normal(0.2, 0.03, n).clip(0),            # throughput (canari seul)
        np.zeros(n),                                 # errors_5xx : constant
        rng.normal(0.6, 0.1, n).clip(0),             # request_rate
    ])


def test_sans_plancher_un_modele_reel_ignore_le_canari():
    # Démonstration du problème : colonnes constantes ignorées, canari KO = score nominal.
    model, normalizer = fit(_nominal_reel())
    base = dict(zip(FEATURE_NAMES, _nominal_reel()[0]))
    ko = {**base, "canary_up": 0.0, "canary_success_ratio": 0.0}
    assert abs(score_one(model, normalizer, ko) - score_one(model, normalizer, base)) < 0.05


def test_plancher_de_variabilite_rend_le_canari_visible():
    from anomaly import with_noise_floor
    data = with_noise_floor(_nominal_reel())
    assert data[:, 1].std() > 0 and data[:, 4].std() > 0      # plus aucune colonne constante
    assert data[:, :2].max() <= 1.0 and data.min() >= 0.0       # bornes physiques respectées
    model, normalizer = fit(data)
    base = dict(zip(FEATURE_NAMES, _nominal_reel()[0]))
    assert score_one(model, normalizer, base) < 0.5
    # Canari KO seul : au-delà du 99e centile du nominal (0,5), sans dépasser forcément le seuil
    # (une dégradation sur un seul axe reste une limite connue, voir ml/README.md).
    ko = {**base, "canary_up": 0.0, "canary_success_ratio": 0.0}
    assert score_one(model, normalizer, ko) > 0.5
    degrade = {**base, "canary_success_ratio": 0.5, "latency_p95": 2.0, "errors_5xx": 0.5, "request_rate": 11.0}
    assert score_one(model, normalizer, degrade) >= 0.7
