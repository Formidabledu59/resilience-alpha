## Objet

<!-- Que fait cette PR et pourquoi ? Lien vers l'issue si elle existe. -->

## Pilier

- [ ] dev
- [ ] infra
- [ ] ia
- [ ] cyber
- [ ] gouv

## Changements

-

## Comment tester

```bash

```

## Vérifications

- [ ] Branche nommée `feat|fix/<pilier>-<sujet>` ou `chore/<sujet>`, commits Conventional Commits en français
- [ ] Aucun secret en clair ; nouvelles variables ajoutées dans `.env.example` avec des valeurs factices
- [ ] Noms de services, réseaux et ports conformes à `CLAUDE.md` (seul le `waf` publié sur le réseau, admin sur `127.0.0.1`)
- [ ] Service : `Dockerfile`, `README.md`, healthcheck, `/metrics`, tests `pytest`
- [ ] Conteneur non-root, `read_only` et `cap_drop: [ALL]` si compatible
- [ ] Fins de ligne LF pour les scripts, Dockerfile et YAML
- [ ] Documentation mise à jour (`README.md` du dossier, runbooks si besoin)
- [ ] CI verte

## Impact sur la démonstration

<!-- Ce changement touche-t-il le scénario attaque → détection → remédiation → transaction de contrôle ? -->
