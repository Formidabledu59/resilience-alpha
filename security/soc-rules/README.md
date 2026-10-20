# security/soc-rules : règles de détection (SOC)

Règles d'alerte évaluées par le **ruler de Loki** sur les journaux, et envoyées à **Alertmanager**.

```
Logs (WAF, auth-service) -> Loki -> ruler (ces règles) -> Alertmanager -> (plus tard) remediation-engine
```

| Fichier | Contenu |
|---|---|
| `alerts.yml` | Règles LogQL : blocages ModSecurity, saturation du rate-limit, scanner détecté, échecs de connexion répétés |

## Comment c'est branché

- Loki monte ce dossier sur `/etc/loki/rules/fake/` (tenant unique, `auth_enabled: false`).
- Le ruler (configuré dans `infra/loki/loki-config.yml`) évalue les règles toutes les 15 s et envoie les alertes à `http://alertmanager:9093`.
- Vérifier les règles chargées : `GET http://loki:3100/loki/api/v1/rules` ; leur état : `GET http://loki:3100/prometheus/api/v1/rules`.

## Règles

| Alerte | Déclencheur | Sévérité |
|---|---|---|
| `WafBlocagesModSecurity` | plus de 10 réponses 403 du WAF en 2 min | warning |
| `WafRateLimitSature` | plus de 100 réponses 429 du WAF en 2 min | warning |
| `WafScannerDetecte` | règle CRS 913xxx (scanner) déclenchée | info |
| `EchecsConnexionRepetes` | plus de 20 échecs d'authentification (401) en 2 min | warning |

Les seuils sont calibrés pour la démo (trafic faible) : à ajuster selon le trafic nominal observé dans Grafana.

## Tester

Depuis le PC Hôte, avec la plateforme démarrée :

```powershell
# Générer des blocages (injections refusées par le WAF)
1..15 | ForEach-Object { curl.exe -s -o NUL "http://127.0.0.1/api/accounts/ACC-001?id=1%27%20OR%20%271%27=%271" }
```

Après environ 1 à 2 minutes, l'alerte `WafBlocagesModSecurity` passe `pending` puis `firing` (vérifiable via l'API du ruler), et apparaît dans Alertmanager. Vérifié au runtime : `inactive -> pending -> firing`, alerte reçue par Alertmanager.
