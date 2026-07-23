FROM node:20-alpine AS builder
# 使用阿里云 Alpine 镜像源加速
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories

WORKDIR /app
COPY package.json package-lock.json* ./
# 使用淘宝 npm 镜像源加速
RUN npm ci --registry=https://registry.npmmirror.com
COPY . .
RUN npm run build

FROM nginx:alpine
# 使用阿里云 Alpine 镜像源加速
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
