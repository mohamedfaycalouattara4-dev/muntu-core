# syntax=docker/dockerfile:1.7
# =============================================================================
# KALYCE · Image frontend — build Vite puis service Nginx durci (ADR-0002)
# =============================================================================

FROM node:20.17.0-bookworm-slim AS builder
ENV CI=true
WORKDIR /src
COPY package.json package-lock.json* ./
# npm ci si un lock est présent, sinon install déterministe minimale.
RUN if [ -f package-lock.json ]; then npm ci; else npm install --no-audit --no-fund; fi
COPY . .
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.27.1-alpine AS runtime
USER 0
RUN rm -rf /usr/share/nginx/html/*
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /src/dist /usr/share/nginx/html
RUN chown -R 101:101 /usr/share/nginx/html
USER 101
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
  CMD wget -q --spider http://127.0.0.1:8080/healthz || exit 1
