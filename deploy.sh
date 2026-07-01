#!/usr/bin/env bash
set -euo pipefail

echo "=== 构建后端镜像 (无缓存) ==="
docker-compose build --no-cache backend

echo ""
echo "=== 构建前端镜像 (无缓存) ==="
docker-compose build --no-cache frontend

echo ""
echo "=== 启动服务 ==="
docker-compose up -d

echo ""
echo "=== 部署完成 ==="
echo "前端: http://localhost:8080"
echo "后端: http://localhost:8000"
