# Stage 1: Download Source
FROM alpine/git:latest as downloader
WORKDIR /src
ARG VERSION
RUN git clone --depth 1 --branch ${VERSION} https://github.com/goharbor/harbor.git .

# Stage 2: Final Image
FROM nginxinc/nginx-unprivileged:alpine
# Copy base configs from source
COPY --from=downloader /src/make/common/config/nginx/nginx.conf /etc/nginx/nginx.conf
# Additional setup might be required for Nginx to run strictly as Harbor's proxy, usually involves templates
# For the purpose of "immutable image from source", having the base Nginx with Harbor's base config is the goal.
