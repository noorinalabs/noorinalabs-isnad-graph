FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
# package-lock.json references @noorinalabs/design-system via a file: path
# pointing at /noorinalabs-design-system-0.0.1.tgz. The deploy script stages
# this tarball into the build context root before docker build (see #818).
# Long-term: switch to GHCR-published image (#817) or npm registry
# (design-system#57) and drop this implicit-contract copy.
COPY noorinalabs-design-system-0.0.1.tgz /
RUN npm ci
# Cache-bust: ARG changes invalidate all subsequent layers
ARG CACHEBUST=1
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
