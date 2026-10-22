# attack/ : scénarios Red Team (PC Attaquant)

Scripts de test offensif exécutés **depuis le PC Attaquant**, connecté au point d'accès `RESILIENCE-G16`.
Ils servent la démonstration : provoquer un incident visible, que la plateforme détecte et répare seule.

> ⚠️ **Cadre strict.** Ces scripts ne visent que le SI du groupe 16, sur `192.168.137.0/24`. Toute autre cible est **refusée** par un garde-fou commun ([`_target_guard.py`](_target_guard.py)) avant la moindre requête. Données exclusivement fictives.

## Prérequis (PC Attaquant)

- Python 3.11+ et aucun composant défensif (voir `README.md` racine, section 4).
- Point d'accès `RESILIENCE-G16` actif, PC Attaquant connecté dessus.
- Installer la dépendance :

  ```bash
  pip install -r attack/requirements.txt
  ```

## Garde-fou commun

`_target_guard.py` résout l'hôte de la cible et refuse (code de sortie 2) toute IP hors `192.168.137.0/24`. Chaque script l'appelle **avant** d'émettre du trafic. Ne pas le contourner.

```
[OK] Cible autorisée : 192.168.137.1 -> 192.168.137.1 (dans 192.168.137.0/24)
[REFUS] Cible interdite : example.com -> 93.184.x.x n'est pas dans 192.168.137.0/24. Aborté.
```

## Scénarios

| Dossier | Script | But | Effet attendu |
|---|---|---|---|
| [`dos/`](dos/) | `flood.py` | Charge applicative contre payment-api | Dégradation visible : succès du canari en baisse (83 % au plus bas le 22/10), latence p95 multipliée par 7, score ML au-dessus du seuil, remédiation déclenchée |
| [`sqli/`](sqli/) | `inject.py` | Injections SQL / XSS / etc. | Toutes bloquées par le WAF (403), tracées dans le SOC |

## Pendant l'attaque, observer

- **Dashboard de supervision** : <http://127.0.0.1:5173> (phase qui passe à « Pendant », puis « Remédiation », puis « Après »).
- **Grafana** : <http://127.0.0.1:3000>, dashboards « Vue globale » et « Frontal et sécurité ».
- **Prometheus** : <http://127.0.0.1:9090>, métrique `canary_up`.

## Vérification de l'IP source (à faire avec l'infra)

À faire une fois, depuis le PC Attaquant, point d'accès actif :

```bash
curl http://192.168.137.1/
```

Puis, dans Grafana (Loki), regarder le champ `client` du journal du WAF. S'il affiche l'IP de la passerelle Docker (ex. `172.x.x.x`) et non l'IP du PC Attaquant, c'est la limite documentée dans [`security/waf/README.md`](../security/waf/README.md) : le ban d'IP coupe tout le trafic externe, le canary interne prouve quand même la reprise.
