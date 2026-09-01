FROM node:18-alpine AS builder
WORKDIR /app

# Install dependencies
COPY package.json package-lock.json ./
RUN npm ci --silent

# Copy source code and build
COPY . ./
RUN npm run build

# ---- Production image ----
FROM nginx:stable-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
# Optional: expose default nginx port
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
