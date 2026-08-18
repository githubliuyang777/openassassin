#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# openAssassin 一键部署脚本
# 从 DockerHub 拉取预构建镜像并启动
#
# 用法:
#   ./deploy.sh                          # 使用默认配置
#   DOCKERHUB_REPO=yourname/openassassin ./deploy.sh
#   IMAGE_TAG=v1.0.0 ./deploy.sh         # 指定版本
#   ./deploy.sh --build                  # 本地构建镜像（不拉取）
#
# 环境变量:
#   DOCKERHUB_REPO  - DockerHub 仓库名 (默认: githubliuyang777/openassassin)
#   IMAGE_TAG       - 镜像标签 (默认: latest)
# ============================================================

DOCKERHUB_REPO="${DOCKERHUB_REPO:-openassassin/openassassin}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
MODE="pull"

# 解析参数
if [[ "${1:-}" == "--build" ]]; then
    MODE="build"
fi

echo "=========================================="
echo " openAssassin 部署"
echo "=========================================="
echo "仓库: ${DOCKERHUB_REPO}"
echo "标签: ${IMAGE_TAG}"
echo "模式: ${MODE}"
echo "=========================================="

# 检查 docker 和 docker compose
if ! command -v docker &> /dev/null; then
    echo "❌ 未安装 Docker，请先安装"
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo "❌ 未安装 Docker Compose V2，请升级 Docker"
    exit 1
fi

# 创建数据目录
mkdir -p data

# 停止旧容器
echo ""
echo ">>> 停止旧容器..."
docker compose down 2>/dev/null || true

if [[ "$MODE" == "pull" ]]; then
    # 从 DockerHub 拉取镜像
    echo ""
    echo ">>> 拉取后端镜像: ${DOCKERHUB_REPO}-backend:${IMAGE_TAG}"
    docker pull "${DOCKERHUB_REPO}-backend:${IMAGE_TAG}"

    echo ""
    echo ">>> 拉取前端镜像: ${DOCKERHUB_REPO}-frontend:${IMAGE_TAG}"
    docker pull "${DOCKERHUB_REPO}-frontend:${IMAGE_TAG}"

    # 使用 pull compose 文件启动
    echo ""
    echo ">>> 启动服务..."
    DOCKERHUB_REPO="${DOCKERHUB_REPO}" IMAGE_TAG="${IMAGE_TAG}" \
        docker compose -f docker-compose.pull.yml up -d
else
    # 本地构建
    echo ""
    echo ">>> 本地构建后端镜像..."
    docker compose build --no-cache backend

    echo ""
    echo ">>> 本地构建前端镜像..."
    docker compose build --no-cache frontend

    echo ""
    echo ">>> 启动服务..."
    docker compose up -d
fi

# 等待服务启动
echo ""
echo ">>> 等待服务启动..."
sleep 3

# 检查容器状态
echo ""
echo ">>> 容器状态:"
docker compose ps 2>/dev/null || docker compose -f docker-compose.pull.yml ps

# 健康检查
echo ""
echo ">>> 健康检查..."
for i in $(seq 1 10); do
    if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
        echo "✅ 后端服务正常"
        break
    fi
    if [[ $i -eq 10 ]]; then
        echo "⚠️  后端服务启动超时，请检查日志: docker compose logs backend"
    fi
    sleep 2
done

echo ""
echo "=========================================="
echo " ✅ 部署完成"
echo "=========================================="
echo "前端: http://localhost:8080"
echo "后端: http://localhost:8000"
echo ""
echo "默认账号: admin / admin"
echo "=========================================="
