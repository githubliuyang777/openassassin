#!/usr/bin/env bash
# openAssassin SQLite 在线备份脚本
# 用法: bash scripts/backup.sh [保留天数,默认30]
# 建议: 每日 cron 执行 — 0 2 * * * cd /path/to/openassassin && bash scripts/backup.sh

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${1:-30}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/ops-${TIMESTAMP}.db"

mkdir -p "${BACKUP_DIR}"

echo "[$(date)] 开始备份 SQLite..."

# 使用 Python sqlite3 .backup() — 在线热备份, 不锁库, WAL 模式安全
docker compose exec -T backend python3 -c "
import sqlite3, os
src = sqlite3.connect('data/ops.db')
dst = sqlite3.connect('/backups/ops-${TIMESTAMP}.db')
src.backup(dst)
dst.close()
src.close()
print(f'备份完成: /backups/ops-${TIMESTAMP}.db ({os.path.getsize(\"/backups/ops-${TIMESTAMP}.db\")} bytes)')
" 2>&1

# 清理过期备份
echo "[$(date)] 清理 ${RETENTION_DAYS} 天前的旧备份..."
find "${BACKUP_DIR}" -name "ops-*.db" -mtime "+${RETENTION_DAYS}" -delete 2>/dev/null || true

# 列出当前备份
echo "[$(date)] 当前备份文件:"
ls -lh "${BACKUP_DIR}"/ops-*.db 2>/dev/null | tail -5 || echo "  (无)"

echo "[$(date)] 备份完成."
