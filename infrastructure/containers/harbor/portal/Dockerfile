# Stage 1: Download Source
FROM alpine/git:latest as downloader
WORKDIR /src
ARG VERSION
RUN git clone --depth 1 --branch ${VERSION} https://github.com/goharbor/harbor.git .

# Stage 2: Build Frontend
FROM node:20 as builder
WORKDIR /src
COPY --from=downloader /src/src/portal .
RUN npm install && npm run build

# Stage 3: Final Immutable Image (Nginx to serve static files)
FROM nginxinc/nginx-unprivileged:alpine
COPY --from=builder /src/dist /usr/share/nginx/html
