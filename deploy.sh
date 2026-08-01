#!/usr/bin/env bash
# openAssassin 一键部署脚本 (Docker Compose v2)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== 检查 .env ==="
if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    echo "未找到 .env，从 .env.example 复制..."
    cp .env.example .env
    # 自动生成强随机密钥
    echo "生成随机 JWT_SECRET..."
    sed -i "s/JWT_SECRET=.*/JWT_SECRET=$(openssl rand -hex 32)/" .env
    echo "生成随机 MASTER_KEY..."
    sed -i "s/MASTER_KEY=.*/MASTER_KEY=$(openssl rand -hex 32)/" .env
    echo "生成随机 ADMIN_DEFAULT_PASSWORD..."
    ADMIN_PW=$(openssl rand -hex 8)
    sed -i "s/ADMIN_DEFAULT_PASSWORD=.*/ADMIN_DEFAULT_PASSWORD=${ADMIN_PW}/" .env
    echo "  -> 管理员初始密码: ${ADMIN_PW} (请登录后立即修改!)"
  else
    echo "错误: .env 和 .env.example 都不存在，无法继续"
    exit 1
  fi
else
  echo ".env 已存在，跳过自动生成"
fi

echo ""
echo "=== 准备数据目录 ==="
mkdir -p data backups
chown -R 10001:10001 data backups 2>/dev/null || echo "  (跳过 chown, 可能需要 sudo)"

echo ""
echo "=== 构建镜像 ==="
docker compose build

echo ""
echo "=== 启动服务 ==="
docker compose up -d

echo ""
echo "=== 等待健康检查 ==="
for i in $(seq 1 30); do
  if curl -sf http://localhost:8000/api/health >/dev/null 2>&1; then
    echo "后端健康检查通过!"
    break
  fi
  echo "  等待后端启动... ($i/30)"
  sleep 2
done

echo ""
echo "=== 部署完成 ==="
echo "前端: http://localhost:8080"
echo "后端: http://localhost:8000"
echo "请立即登录并修改管理员密码!"
