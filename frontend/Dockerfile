# Node 24 is pre-LTS (LTS expected 2026-06-02). Pinned to a specific release to
# avoid pre-LTS churn. Revisit after LTS promotion to use node:24-alpine.
# See: https://nodejs.org/en/about/previous-releases
FROM node:24.14.1-alpine AS build
WORKDIR /app
RUN npm install -g npm@11.12.1
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.28.3-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
