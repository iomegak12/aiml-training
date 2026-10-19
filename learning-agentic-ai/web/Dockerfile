# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1: build the React app with Vite
# ---------------------------------------------------------------------------
FROM node:22-alpine AS build

WORKDIR /app

# Dependencies first (cached unless package*.json change)
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund

COPY index.html vite.config.js ./
COPY public ./public
COPY src ./src
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2: nginx serving the static build and proxying /api to the API
# ---------------------------------------------------------------------------
FROM nginx:1.28-alpine AS runtime

RUN rm -f /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/corvana.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1/healthz || exit 1
