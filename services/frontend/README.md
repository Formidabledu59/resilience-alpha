# frontend

Interface client de paiement (React 19 + Tailwind CSS 4, build Vite), servie par nginx non-root (uid 101, port 8080).
Contrat des API appelées : [`docs/architecture/contracts.md`](../../docs/architecture/contracts.md).

## Pages

| Chemin | Contenu | Action principale (une seule par page) |
|---|---|---|
| `/` | Connexion puis virement entre comptes fictifs, soldes | « Se connecter », puis « Valider le paiement » |
| `/confidentialite` | Page RGPD : données traitées, finalités, durée, droits | aucune |
| `/cgu` | Conditions générales d'utilisation | aucune |
| toute autre adresse | Page 404 personnalisée, avec le vrai code HTTP 404 | lien de retour |

La liste des pages est définie une seule fois dans `src/routes.js`. Les tests vérifient que `nginx.conf` et `public/sitemap.xml` déclarent exactement les mêmes chemins, et que chaque lien interne pointe vers une page ou un fichier existant.

## Fonctionnement

- Le navigateur n'appelle que `/api/*` sur la même origine. Le nginx du frontal relaie vers `auth-service` (`/api/auth/token`) et `payment-api` (`/api/transactions`, `/api/accounts/<id>`). **Aucun secret ni adresse de service dans le code du navigateur.**
- Le jeton JWT est gardé dans `sessionStorage` (effacé à la fermeture de l'onglet). Aucun cookie.
- En démonstration, le frontal est joignable uniquement à travers le WAF (`http://192.168.137.1`).

## Check-list qualité et conformité

| Point | Mise en oeuvre |
|---|---|
| Page RGPD | `/confidentialite` |
| Page de CGU | `/cgu` |
| API hors front-end | Toute la logique et les données côté API ; le navigateur passe par `/api` |
| HTTPS | Hors périmètre du laboratoire (réseau local, pas de nom de domaine ni de certificat). À faire au WAF : redirection 80 vers 443 et en-tête HSTS |
| Bannière cookies | Bandeau d'information : aucun cookie ni traceur, seul un stockage strictement nécessaire (pas de consentement requis) |
| Meta title | Titre propre à chaque page (`document.title`), description dans `index.html` |
| Image réseaux | `public/og-image.png` (1200 x 630, 12 Ko), balises Open Graph et Twitter |
| Favicon | `favicon.svg`, `favicon-32.png`, `apple-touch-icon.png` |
| Sitemap et robots.txt | `public/sitemap.xml`, `public/robots.txt` (`/api/` exclu) |
| Textes des images | Attribut `alt` sur chaque image (vide pour le logo décoratif) |
| Compression des images | PNG en palette optimisée, logo en SVG |
| Vitesse des pages | JS 74 Ko et CSS 4 Ko après gzip, cache d'un an sur les fichiers à empreinte, aucune police externe |
| Contraste | Couleurs AA (au moins 4,5:1) : texte `slate-900`, bouton `#1d4ed8` sur blanc, erreurs `red-700` |
| Site responsive | Mise en page Tailwind mobile d'abord (`sm:`), boutons pleine largeur sur mobile |
| Page 404 | `public/404.html`, code HTTP 404 réel |
| Liens cassés | Test automatique (`tests/routes.test.js`) et tableau des 404 dans Grafana |
| Validation des formulaires | Côté navigateur (`src/validation.js`, messages accessibles) et côté serveur (payment-api) |
| Anti-spam | Champ piège invisible + rate-limit nginx (connexion 10/min, API 10/s) |
| Outil d'analytics | Mesure d'audience sans cookie : journaux nginx JSON **sans adresse IP**, collectés par Alloy dans Loki, dashboard Grafana « Resilience - Frontal et sécurité » |
| Un seul CTA | Un seul bouton d'action principal par écran |
| Typographie | Test automatique (`tests/typography.test.js`) : pas de tiret cadratin ou demi-cadratin, pas de caractère « points de suspension », pas de guillemets courbes, pas d'espace insécable, pas de puces typographiques ni de caractères invisibles |

En-têtes de sécurité envoyés par nginx : `Content-Security-Policy` stricte (aucune ressource externe, pas d'iframe), `X-Frame-Options: DENY`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, version de nginx masquée.

## Développement et tests

Les tests et le build tournent dans le conteneur Node du projet (le npm 10 livré avec Node 22 plante sur l'arbre de dépendances de vitest 5 ; npm 11.21.0 est épinglé) :

```powershell
docker run --rm -v "${PWD}/services/frontend:/app" -v resilience-fe-nm:/app/node_modules -w /app node:22.23.3-alpine3.24 sh -c "npm install -g npm@11.21.0 && npm ci && npm test && npm run build"
```

Avant la mise en place du WAF, le frontal peut être ouvert sur le PC Hôte avec la surcharge de développement (publication sur `127.0.0.1:8081` uniquement) :

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build frontend
# puis http://127.0.0.1:8081
```
