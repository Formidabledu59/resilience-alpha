from conftest import make_incident, sample_evidence
from incidents import attack_types, classify, observed_errors, report_markdown


def test_classification_des_alertes():
    assert classify("WafRateLimitSature") == "dos"
    assert classify("WafBlocagesModSecurity") == "attaque_applicative"
    assert classify("AnomalieML") == "anomalie"
    assert classify("Inconnue") == "autre"


def test_types_d_attaque_regroupes_par_famille_de_regles():
    types = attack_types(sample_evidence())
    assert [t["label"] for t in types] == ["Injection SQL", "Cross-site scripting (XSS)"]
    assert types[0] == {"label": "Injection SQL", "count": 35, "rules": ["942100", "942190"]}


def test_erreurs_observees_avec_leur_signification():
    errors = observed_errors(sample_evidence(canary_min=0.4, limited=300))
    kinds = {e["type"]: e for e in errors}
    assert kinds["HTTP 403"]["count"] == 42
    assert kinds["HTTP 429"]["count"] == 300
    assert "40,0 %" in kinds["Échec canari"]["detail"]
    assert "HTTP 401" not in kinds  # aucune erreur d'authentification : pas de ligne vide


def test_bilan_attaque_bloquee_sans_impact():
    incident = make_incident()
    summary = incident["summary"]
    assert "Injection SQL" in summary["what_happened"]
    assert "172.23.0.1" in summary["what_happened"]
    assert summary["impact"].startswith("Aucun impact métier")
    assert incident["defenses"][0]["layer"] == "WAF ModSecurity (OWASP CRS)"
    assert "942100" in incident["defenses"][0]["result"]
    assert summary["outcome"].startswith("Reprise prouvée")
    assert summary["durations"]["open_to_close_seconds"] == 75


def test_bilan_service_degrade():
    incident = make_incident(category="dos", evidence=sample_evidence(canary_min=0.5, limited=500))
    assert incident["summary"]["impact"].startswith("Service dégradé : taux de succès du canari descendu à 50,0 %")
    assert any(d["layer"] == "WAF rate-limit" for d in incident["defenses"])


def test_rapport_markdown_complet():
    report = report_markdown(make_incident(), journal_hash="ab" * 32)
    for section in ("# Rapport d'incident inc-2026-10-20-001", "## Ce qui s'est passé", "## Erreurs observées",
                    "## Défense", "## Chronologie", "## Issue", "ab" * 32):
        assert section in report
