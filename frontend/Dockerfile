FROM node:18-alpine AS builder
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --silent

COPY . ./

# Vite inlines VITE_* env vars into the JS bundle at BUILD time — setting
# them under docker-compose's `environment:` for this service has no effect
# on an already-built static bundle. They must come in as build ARGs here
# and be exported as ENV before `npm run build` runs.
ARG VITE_API_URL=http://localhost:8000
ARG VITE_API_KEY
ENV VITE_API_URL=${VITE_API_URL}
ENV VITE_API_KEY=${VITE_API_KEY}

RUN npm run build

# ---- Production image ----
FROM nginx:stable-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q -O /dev/null http://localhost/ || exit 1
CMD ["nginx", "-g", "daemon off;"]
