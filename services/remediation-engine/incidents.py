"""Bilan d'un incident : classification, erreurs observées, défenses, résumé et rapport.

Fonctions pures (aucun appel réseau) : elles transforment les alertes et les preuves collectées
en un état des lieux lisible par un opérateur ou un jury. Testées dans tests/test_incidents.py.
Les textes n'utilisent que de la ponctuation simple (règles typographiques du dashboard).
"""

from datetime import datetime

ACTIVE_STATUSES = ("OPEN", "REMEDIATING", "VERIFYING")

CATEGORIES = {
    "attaque_applicative": "Attaque applicative",
    "dos": "Déni de service applicatif",
    "reconnaissance": "Reconnaissance (scanner de vulnérabilités)",
    "force_brute": "Force brute sur l'authentification",
    "indisponibilite": "Indisponibilité d'un service",
    "anomalie": "Anomalie de comportement (détection ML)",
    "autre": "Alerte non classée",
}

# Alertes connues (règles SOC Loki et règles Prometheus) -> catégorie d'incident
ALERT_CATEGORY = {
    "WafBlocagesModSecurity": "attaque_applicative",
    "WafRateLimitSature": "dos",
    "WafScannerDetecte": "reconnaissance",
    "EchecsConnexionRepetes": "force_brute",
    "TargetDown": "indisponibilite",
    "AnomalieML": "anomalie",
}

SOURCES = {"alertmanager": "les règles SOC (Alertmanager)", "ml-detector": "le détecteur ML (Isolation Forest)"}

# Familles de règles OWASP CRS : les 3 premiers chiffres de l'identifiant de règle
RULE_FAMILIES = {
    "913": "Scanner de vulnérabilités",
    "920": "Violation du protocole HTTP",
    "921": "Attaque sur le protocole HTTP",
    "930": "Accès à des fichiers système (LFI)",
    "931": "Inclusion de fichier distant (RFI)",
    "932": "Exécution de commande (RCE)",
    "933": "Injection PHP",
    "934": "Injection Node.js",
    "941": "Cross-site scripting (XSS)",
    "942": "Injection SQL",
    "943": "Fixation de session",
    "944": "Attaque Java (Log4Shell)",
}

# Signification des erreurs observées, affichée telle quelle dans le bilan
ERROR_MEANINGS = {
    "HTTP 403": "Requête bloquée par le WAF (règle ModSecurity ou liste de bannissement)",
    "HTTP 429": "Requête rejetée par le rate-limit du WAF (débit excessif)",
    "HTTP 401": "Échec d'authentification sur auth-service",
    "HTTP 5xx": "Erreur serveur des API (service saturé ou en panne)",
    "Échec canari": "Transaction de paiement de contrôle en échec (impact métier réel)",
}


def classify(alert_name: str) -> str:
    return ALERT_CATEGORY.get(alert_name, "autre")


def rule_family(rule_id: str) -> str:
    return RULE_FAMILIES.get(str(rule_id)[:3], "Autre règle du Core Rule Set")


def fr_number(value: float, digits: int = 0) -> str:
    text = f"{value:,.{digits}f}"
    return text.replace(",", " ").replace(".", ",")


def fr_percent(ratio: float | None) -> str:
    return "-" if ratio is None else f"{fr_number(ratio * 100, 1)} %"


def fr_seconds(seconds: float | None) -> str:
    if seconds is None:
        return "-"
    if seconds < 1:
        return f"{fr_number(seconds * 1000)} ms"
    if seconds < 90:
        return f"{fr_number(seconds, 1)} s"
    minutes, rest = divmod(int(round(seconds)), 60)
    return f"{minutes} min {rest:02d} s"


def _elapsed(start: str | None, end: str | None) -> float | None:
    if not start or not end:
        return None
    return (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()


def attack_types(evidence: dict | None) -> list[dict]:
    """Types d'attaque identifiés à partir des règles WAF déclenchées, regroupés par famille."""
    families: dict[str, dict] = {}
    for item in (evidence or {}).get("waf", {}).get("rules") or []:
        label = rule_family(item["rule"])
        family = families.setdefault(label, {"label": label, "count": 0, "rules": []})
        family["count"] += item["count"]
        family["rules"].append(item["rule"])
    return sorted(families.values(), key=lambda f: f["count"], reverse=True)


def observed_errors(evidence: dict | None) -> list[dict]:
    """Types d'erreurs observés pendant la fenêtre de l'incident, avec leur nombre et leur sens."""
    evidence = evidence or {}
    waf = evidence.get("waf") or {}
    metrics = evidence.get("metrics") or {}
    errors = []

    def add(kind: str, count, detail: str | None = None):
        if count:
            errors.append({"type": kind, "count": count, "meaning": ERROR_MEANINGS[kind], "detail": detail})

    add("HTTP 403", waf.get("blocked_403"))
    add("HTTP 429", waf.get("rate_limited_429"))
    add("HTTP 401", evidence.get("auth_failures"))
    peak_5xx = metrics.get("errors_5xx_peak")
    if peak_5xx:
        errors.append({"type": "HTTP 5xx", "count": None, "meaning": ERROR_MEANINGS["HTTP 5xx"],
                       "detail": f"pic à {fr_number(peak_5xx, 2)} erreurs par seconde"})
    worst = metrics.get("canary_success_min")
    if worst is not None and worst < 0.99:
        errors.append({"type": "Échec canari", "count": None, "meaning": ERROR_MEANINGS["Échec canari"],
                       "detail": f"taux de succès descendu à {fr_percent(worst)}"})
    return errors


def defenses(incident: dict) -> list[dict]:
    """Comment la plateforme s'est défendue : couches de protection puis actions automatiques."""
    evidence = (incident.get("evidence") or {}).get("closing") or (incident.get("evidence") or {}).get("opening") or {}
    waf = evidence.get("waf") or {}
    result = []
    if waf.get("blocked_403"):
        types = ", ".join(f"{t['label']} ({', '.join(t['rules'][:3])})" for t in attack_types(evidence)) or "liste de bannissement"
        result.append({"layer": "WAF ModSecurity (OWASP CRS)", "action": f"{fr_number(waf['blocked_403'])} requêtes bloquées (403)",
                       "result": f"Règles déclenchées : {types}"})
    if waf.get("rate_limited_429"):
        result.append({"layer": "WAF rate-limit", "action": f"{fr_number(waf['rate_limited_429'])} requêtes excédentaires rejetées (429)",
                       "result": "Afflux absorbé avant d'atteindre les API"})
    for step in incident.get("steps", []):
        if step.get("kind") == "action":
            result.append({"layer": "Moteur de remédiation", "action": step["action"], "result": step.get("result")})
        elif step.get("kind") == "verification":
            result.append({"layer": "Vérification métier", "action": step["action"], "result": step.get("result")})
    return result


def summary(incident: dict) -> dict:
    """Résumé en phrases : ce qui s'est passé, l'impact, la défense et l'issue."""
    evidence = incident.get("evidence") or {}
    closing = evidence.get("closing") or {}
    opening = evidence.get("opening") or {}
    best = closing or opening
    metrics = best.get("metrics") or {}
    waf = best.get("waf") or {}

    names = ", ".join(sorted({a["name"] for a in incident.get("alerts", [])}))
    what = f"{incident['category_label']} détectée par {SOURCES.get(incident['source'], incident['source'])} (alerte {names})."
    types = attack_types(best)
    if types:
        what += " Types identifiés : " + ", ".join(t["label"] for t in types) + "."
    clients = waf.get("clients") or []
    if clients:
        what += " Origine : " + ", ".join(f"{c['ip']} ({fr_number(c['count'])} requêtes refusées)" for c in clients[:3]) + "."

    worst = metrics.get("canary_success_min")
    if worst is None:
        impact = "Impact métier non mesuré (canari indisponible pendant la collecte)."
    elif worst >= 0.99:
        impact = "Aucun impact métier : le canari est resté à 100 % de transactions réussies."
    else:
        impact = f"Service dégradé : taux de succès du canari descendu à {fr_percent(worst)}"
        if metrics.get("latency_p95_peak") is not None:
            impact += f", latence p95 jusqu'à {fr_seconds(metrics['latency_p95_peak'])}"
        if metrics.get("errors_5xx_peak"):
            impact += f", {fr_number(metrics['errors_5xx_peak'], 2)} erreurs 5xx par seconde"
        impact += "."

    layers = defenses(incident)
    defense = " ; ".join(f"{d['layer']} : {d['action']}" for d in layers) + "." if layers else "Aucune défense enregistrée pour l'instant."

    status = incident["status"]
    probe = next((s for s in reversed(incident.get("steps", [])) if s.get("kind") == "verification" and "contrôle" in s["action"]), None)
    if status == "CLOSED":
        outcome = f"Reprise prouvée par une transaction de contrôle réussie ({probe['result'] if probe else 'COMPLETED'})."
    elif status == "FAILED":
        last = incident["steps"][-1] if incident.get("steps") else {}
        outcome = f"Reprise non prouvée : {last.get('action', '')} ({last.get('result', '')}). Intervention humaine requise."
    else:
        outcome = "Incident en cours de traitement."

    first_alert = min((a["at"] for a in incident.get("alerts", [])), default=incident["opened_at"])
    return {
        "what_happened": what,
        "impact": impact,
        "defense": defense,
        "outcome": outcome,
        "durations": {
            "detection_to_open_seconds": _elapsed(first_alert, incident["opened_at"]),
            "open_to_close_seconds": _elapsed(incident["opened_at"], incident.get("closed_at")),
        },
    }


def assess(incident: dict) -> dict:
    """Recalcule le bilan (types d'attaque, erreurs, défenses, résumé) et le range dans l'incident."""
    evidence = incident.get("evidence") or {}
    best = evidence.get("closing") or evidence.get("opening")
    incident["attack_types"] = attack_types(best)
    incident["errors"] = observed_errors(best)
    incident["defenses"] = defenses(incident)
    incident["summary"] = summary(incident)
    return incident


def report_markdown(incident: dict, journal_hash: str | None = None) -> str:
    """Rapport d'incident en Markdown, téléchargeable depuis le dashboard."""
    s = incident.get("summary") or summary(incident)
    durations = s["durations"]
    lines = [
        f"# Rapport d'incident {incident['id']}",
        "",
        "| | |",
        "|---|---|",
        f"| Statut | {incident['status']} |",
        f"| Catégorie | {incident['category_label']} |",
        f"| Gravité | {incident.get('severity', '-')} |",
        f"| Détecté par | {SOURCES.get(incident['source'], incident['source'])} |",
        f"| Ouvert le | {incident['opened_at']} |",
        f"| Clôturé le | {incident.get('closed_at') or '-'} |",
        f"| Durée de traitement | {fr_seconds(durations['open_to_close_seconds'])} |",
        "",
        "## Ce qui s'est passé",
        "",
        s["what_happened"],
        "",
        "## Impact",
        "",
        s["impact"],
        "",
        "## Erreurs observées",
        "",
    ]
    if incident.get("errors"):
        lines += ["| Type | Nombre | Signification | Détail |", "|---|---|---|---|"]
        for e in incident["errors"]:
            count = fr_number(e["count"]) if e.get("count") else "-"
            lines.append(f"| {e['type']} | {count} | {e['meaning']} | {e.get('detail') or '-'} |")
    else:
        lines.append("Aucune erreur relevée dans la fenêtre de l'incident.")
    lines += ["", "## Défense", ""]
    if incident.get("defenses"):
        lines += ["| Couche | Action | Résultat |", "|---|---|---|"]
        lines += [f"| {d['layer']} | {d['action']} | {d.get('result') or '-'} |" for d in incident["defenses"]]
    else:
        lines.append("Aucune défense enregistrée.")
    lines += ["", "## Alertes reçues", "", "| Heure | Alerte | Source | Description |", "|---|---|---|---|"]
    lines += [f"| {a['at']} | {a['name']} | {a['source']} | {a.get('summary') or '-'} |" for a in incident.get("alerts", [])]
    lines += ["", "## Chronologie", "", "| Heure | Étape | Résultat |", "|---|---|---|"]
    lines += [f"| {st['at']} | {st['action']} | {st.get('result') or '-'} |" for st in incident.get("steps", [])]
    lines += ["", "## Issue", "", s["outcome"], ""]
    if journal_hash:
        lines += ["---", "", f"Trace d'audit : journal chaîné SHA-256, dernière empreinte `{journal_hash}`.", ""]
    return "\n".join(lines)
