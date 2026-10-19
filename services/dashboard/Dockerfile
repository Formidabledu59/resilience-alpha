# --- Build : tests puis compilation Vite --------------------------------------
FROM node:22.23.3-alpine3.24 AS build
# npm 10 (fourni avec Node 22) plante sur l'arbre de dépendances de vitest 5 : npm 11 épinglé
RUN npm install -g npm@11.21.0 --no-audit --no-fund
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm test && npm run build

# --- Exécution : fichiers statiques servis par nginx non-root (uid 101, port 8080)
FROM nginxinc/nginx-unprivileged:1.30.4-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
