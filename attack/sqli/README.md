# attack/sqli : injections bloquées par le WAF

Scénario **complémentaire** : une tentative de compromission applicative (injections SQL, XSS, etc.), bloquée par le WAF, tracée et qualifiable dans le SOC. Ici on ne cherche pas l'indisponibilité, mais à montrer la défense qui tient et qui laisse une trace exploitable.

> Lire d'abord [`attack/README.md`](../README.md). Cible restreinte à `192.168.137.0/24`.

## Lancer

```bash
python attack/sqli/inject.py --target http://192.168.137.1
```

Le script envoie une série de charges classiques et affiche, pour chacune, le code HTTP et le verdict :

```
Tentative                                Méthode Code  Verdict
------------------------------------------------------------------------
Injection SQL (paramètre d'URL)          GET     403   BLOQUÉ par le WAF
Injection SQL (UNION)                    GET     403   BLOQUÉ par le WAF
Injection SQL (login)                    POST    403   BLOQUÉ par le WAF
XSS réfléchi                             GET     403   BLOQUÉ par le WAF
Accès à un fichier système               GET     403   BLOQUÉ par le WAF
Log4Shell (en-tête User-Agent)           GET     403   BLOQUÉ par le WAF
```

Code de sortie 0 si tout est bloqué, 1 si une charge passe (à investiguer : règle CRS manquante ou exclusion trop large).

## Ce qu'on doit observer

Dans Grafana, dashboard « Resilience - Frontal et sécurité » :

- **Requêtes refusées par le WAF** : pic de `403`.
- **Règles ModSecurity déclenchées** : identifiants OWASP CRS (942xxx SQLi, 941xxx XSS, 930xxx accès fichiers, 944xxx Log4Shell, 913xxx scanners).
- **Clients bloqués par ModSecurity** : l'IP source (voir la limite d'IP dans [`security/waf/README.md`](../../security/waf/README.md)).

C'est la matière du volet SOC : détection, qualification, et base pour les règles d'alerte de `security/soc-rules/`.
