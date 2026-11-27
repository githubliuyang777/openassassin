FROM node:20-alpine AS builder
# 使用阿里云 Alpine 镜像源加速
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories

WORKDIR /app
COPY package.json package-lock.json* ./
# 使用淘宝 npm 镜像源加速
RUN npm ci --registry=https://registry.npmmirror.com
COPY . .
RUN npm run build

# 官方 -otel 变体内置 ngx_otel_module，避免自行编译/安装模块
# 1.31.10 修复 2026-11 nginx2root 系列（CVE-2026-123007 等）及 ssl_early_data CPU 问题
FROM nginx:1.31.10-alpine-otel
# Compose 默认关闭追踪；K8s 通过 Deployment env 覆盖
ENV OTEL_EXPORTER_ENDPOINT=127.0.0.1:4317 \
    OTEL_TRACE_MODE=off

# load_module 必须在 main context；兼容基础镜像已通过 modules-enabled 加载的情况
RUN set -e; \
    if grep -q 'modules-enabled' /etc/nginx/nginx.conf; then \
        mkdir -p /etc/nginx/modules-enabled; \
        grep -rq 'ngx_otel_module' /etc/nginx/modules-enabled || \
            echo 'load_module modules/ngx_otel_module.so;' > /etc/nginx/modules-enabled/50-otel.conf; \
    else \
        grep -q 'load_module modules/ngx_otel_module.so;' /etc/nginx/nginx.conf || \
            sed -i '1i load_module modules/ngx_otel_module.so;' /etc/nginx/nginx.conf; \
    fi; \
    nginx -t

# 官方 entrypoint 会用 envsubst 渲染到 /etc/nginx/conf.d/default.conf
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
