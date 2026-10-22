FROM python:3.12-alpine

# 使用阿里云 Alpine 镜像源加速
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories

# 创建固定 UID/GID，K8s 侧通过 runAsUser/fsGroup 复用；
# 镜像本身保持默认 root，以兼容 Docker Compose 的 bind mount 和 docker.sock。
RUN addgroup -g 10001 -S app && adduser -u 10001 -S -G app app

WORKDIR /app
COPY --chown=app:app requirements.txt .
# 使用清华 PyPI 镜像源加速
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

COPY --chown=app:app . .

RUN mkdir -p /app/data/logs && chown -R app:app /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
