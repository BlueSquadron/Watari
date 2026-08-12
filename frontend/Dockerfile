# Stage 1: Build
FROM node:20-slim AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
RUN npm run build

# Stage 2: Serve
FROM nginx:alpine

# Copy custom nginx config
COPY --from=build /app/dist /usr/share/nginx/html

# Configure nginx to serve SPA (redirect all routes to index.html)
RUN echo 'server { \
    listen 3000; \
    server_name _; \
    root /usr/share/nginx/html; \
    index index.html; \
    location / { \
        try_files $uri $uri/ /index.html; \
    } \
    location /api { \
        proxy_pass http://api:8000; \
        proxy_set_header Host $host; \
        proxy_set_header X-Real-IP $remote_addr; \
    } \
    location /ws { \
        proxy_pass http://api:8000; \
        proxy_http_version 1.1; \
        proxy_set_header Upgrade $http_upgrade; \
        proxy_set_header Connection "upgrade"; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
