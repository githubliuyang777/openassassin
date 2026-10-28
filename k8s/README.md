# openAssassin Kubernetes 部署

使用 Kustomize 部署 openAssassin。默认形态：

```
Internet
  └─ Ingress (ingress-nginx)
       └─ Service frontend:80 ── Deployment frontend ×2 (nginx)
            └─ /api/ 反代 → Service backend:8000 ── Deployment backend ×1
                 └─ PVC openassassin-data → /app/data (SQLite + 日志)
```

## 前置条件

- Kubernetes 1.25+
- `kubectl` 1.22+（1.21 内置的 kustomize 对非 ASCII 注释有解析缺陷）
- 集群已安装 ingress-nginx，并存在 `IngressClass/nginx`
- 集群有默认 StorageClass（`kubectl get sc`），且必须是块存储（NFS/EFS/CephFS 不适用于 SQLite WAL）；没有默认 SC 时在 `pvc.yaml` 中显式指定
- 可访问 DockerHub（或自行替换镜像地址）

## 1. 镜像

默认使用：

- `openassassin/openassassin-backend:latest`
- `openassassin/openassassin-frontend:latest`

> **重要**：`SANDBOX_ENABLED` 开关是新增配置。请确认后端 `latest` 已包含该版本的代码
> （合并 master 后由 CI 自动构建），否则旧镜像会忽略该变量，执行脚本仍会报 Docker 错误。

> **生产环境请固定 tag**：CI 同时发布 `sha-<12位>` 标签。使用 `latest` 时，
> `kubectl rollout undo` 会重新拉取同一个 `latest`，无法真正回滚；
> 重新 apply 未变更的清单也不会触发镜像更新。请把 `newTag` 改为明确的版本或 `sha-*` 标签。

要使用其他仓库或固定版本，修改 `kustomization.yaml` 的 `images`：

```yaml
images:
  - name: openassassin/openassassin-backend
    newName: registry.example.com/openassassin/backend
    newTag: "1.2.3"
  - name: openassassin/openassassin-frontend
    newName: registry.example.com/openassassin/frontend
    newTag: "1.2.3"
```

私有仓库还需在 Deployment 中增加 `imagePullSecrets`（或给默认 ServiceAccount 绑定）。

## 2. 创建 Namespace 与 Secret

```bash
kubectl apply -f k8s/namespace.yaml

kubectl -n openassassin create secret generic openassassin-secrets \
  --from-literal=JWT_SECRET="$(openssl rand -hex 32)" \
  --from-literal=MASTER_KEY="$(openssl rand -hex 32)" \
  --from-literal=ADMIN_DEFAULT_PASSWORD='<设置一个强密码>' \
  --from-literal=SMTP_PASSWORD=''
```

注意事项：

- **`MASTER_KEY` 必须永久保存且不可更换**。它用于解密数据库中已存储的凭据；一旦变更，
  所有历史密钥将无法解密。
- `ADMIN_DEFAULT_PASSWORD` 只在首次建库（admin 用户不存在）时生效，之后修改 Secret 不会改密。
- 忘记密码可通过登录页「忘记密码」重置（需配置 SMTP）。
- 生产环境建议使用 Sealed Secrets / External Secrets Operator 管理同名 Secret；
  Kustomize 不管理 Secret，`kubectl apply -k` 不会覆盖它。

也可以用模板创建后自行填写（切勿提交填写后的文件）：

```bash
cp k8s/examples/secret.example.yaml k8s/secret.yaml
# 编辑 k8s/secret.yaml
kubectl apply -f k8s/secret.yaml
```

`kubectl apply -f k8s/` 不会递归读取 `examples/` 子目录，因此示例文件不会被误应用。
Secret 必须先于 Deployment 存在，且四个键缺一不可（Deployment 使用逐键 `secretKeyRef`）。

## 3. 配置域名 / TLS

编辑 `k8s/ingress.yaml`，把 `openassassin.example.com` 替换为实际域名。
未安装 ingress-nginx 时，可临时使用 port-forward 访问（见验证章节）。

TLS：先创建证书 Secret（或由 cert-manager 签发），再取消 `ingress.yaml` 中 `tls` 段注释。

## 4. 部署

```bash
kubectl apply -k k8s
kubectl -n openassassin rollout status deploy/backend
kubectl -n openassassin rollout status deploy/frontend
kubectl -n openassassin get pods,svc,pvc,ingress
```

首次启动 backend 会建表、执行数据库迁移并创建 admin 用户。

## 5. 验证

```bash
HOST=openassassin.example.com

# 健康检查（经 Ingress → frontend nginx → backend）
curl -sS -H "Host: $HOST" http://<ingress-ip>/api/health
# {"status":"ok"}

# 登录
TOKEN=$(curl -sS -H "Host: $HOST" -H 'Content-Type: application/json' \
  -X POST http://<ingress-ip>/api/v1/auth/login \
  -d '{"username":"admin","password":"<你的密码>"}' | jq -r .access_token)

# 创建并执行脚本，应返回 [SANDBOX_DISABLED]
SID=$(curl -sS -H "Host: $HOST" -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -X POST http://<ingress-ip>/api/v1/scripts \
  -d '{"name":"k8s-smoke","type":"shell","content":"echo ok","timeout":30}' | jq -r .id)

curl -sS -H "Host: $HOST" -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -X POST \
  http://<ingress-ip>/api/v1/scripts/$SID/execute -d '{}' | jq '{status,exit_code,log}'
```

没有 Ingress / 域名时：

```bash
kubectl -n openassassin port-forward svc/frontend 8080:80
open http://localhost:8080
```

持久化验证：创建一个密钥或修改配置 → `kubectl -n openassassin delete pod -l app=backend`
→ 等待 Pod Ready → 数据仍在。

## 6. 升级与回滚

```bash
# 修改 kustomization.yaml 中的镜像 tag 后
kubectl apply -k k8s
kubectl -n openassassin rollout status deploy/backend

# 回滚
kubectl -n openassassin rollout undo deploy/backend
kubectl -n openassassin rollout undo deploy/frontend
```

修改 Secret 后需重启后端使进程环境变量生效：

```bash
kubectl -n openassassin rollout restart deploy/backend
```

## 7. 备份

SQLite 使用 WAL，不要直接复制运行中的数据库文件。使用 SQLite backup API：

```bash
POD=$(kubectl -n openassassin get pod -l app=backend -o jsonpath='{.items[0].metadata.name}')

kubectl -n openassassin exec "$POD" -- python -c \
  "import sqlite3; s=sqlite3.connect('/app/data/ops.db'); d=sqlite3.connect('/app/data/ops.db.bak'); s.backup(d); d.close(); s.close()"

BACKUP_DIR="${HOME}/openassassin-backups"
mkdir -p "$BACKUP_DIR"
kubectl -n openassassin cp "$POD:/app/data/ops.db.bak" "$BACKUP_DIR/ops-$(date +%F).db"
kubectl -n openassassin exec "$POD" -- rm -f /app/data/ops.db.bak
```

备份文件包含用户、加密凭据与审计日志，**不要放在仓库目录内**（`.gitignore` 已额外忽略
`ops-*.db` 作为兜底）。如需完整备份（含执行日志），可对 PVC 做快照，或停机后复制
`/app/data` 整个目录。

## 8. 与 Docker Compose 的差异

| 项目 | Docker Compose | Kubernetes |
|---|---|---|
| 脚本执行 | Docker 沙箱（挂载 docker.sock） | **暂时禁用**（`SANDBOX_ENABLED=false`），执行返回 `[SANDBOX_DISABLED]` |
| 后端副本 | 1 | 1（SQLite 单写者，禁止扩容/HPA） |
| 数据 | `./data` 目录 | PVC `openassassin-data`（10Gi） |
| 入口 | `:8080` | Ingress → frontend:80 |
| 密钥 | `.env` | Secret `openassassin-secrets` |

> 沙箱禁用期间，每次点击执行仍会创建一条 `failed` 执行记录（日志含
> `[SANDBOX_DISABLED]`），仪表盘成功率会因此下降。这是保持执行状态枚举兼容的取舍。

### 如何重新启用脚本执行

K8s 清单**不挂载** `docker.sock`（安全风险高且托管集群通常不可用）。如需恢复脚本执行，
需要满足以下任一条件后把 `config.env` 中的 `SANDBOX_ENABLED` 改为 `true`：

1. **DooD**：节点必须是 Docker 运行时，并以 hostPath **同路径**挂载
   `/var/run/docker.sock` 与 `/tmp/openassassin-sandbox`。沙箱 daemon 在宿主侧解析
   bind 源路径，两处路径必须一致；同时用 nodeSelector 固定节点。socket 权限等价于
   节点 root，需接受该安全风险。
2. **DinD sidecar**：需要 `privileged: true`，当前 Namespace 的 PSS `baseline` 会拒绝，
   必须先放宽 Pod Security。backend 与 sidecar 需共享一个 emptyDir 并都挂载到
   `/tmp/openassassin-sandbox`，并通过 `DOCKER_HOST` 指向 sidecar 的 Docker daemon。
3. 将执行器改造为 Kubernetes Job/Pod 方案（需代码改动）。

另需注意：前端镜像内 nginx 的 `proxy_read_timeout` 为 3600s，与
`SANDBOX_MAX_TIMEOUT` 相同。重新启用前应重建前端镜像提高超时，或降低
`SANDBOX_MAX_TIMEOUT`，为镜像拉取、容器启动和日志收集留出余量。
长脚本在滚动升级/节点驱逐时仍可能被中断，建议在维护窗口操作。

## 9. 故障排查

```bash
kubectl -n openassassin describe pod -l app=backend
kubectl -n openassassin logs deploy/backend --tail=200
kubectl -n openassassin get events --sort-by=.lastTimestamp
```

常见问题：

| 现象 | 原因 / 处理 |
|---|---|
| PVC 一直 Pending | 集群无默认 StorageClass，或没有可用 PV；检查 `kubectl get sc,pv` |
| 日志出现 `database is locked` / 数据异常 | PVC 落在 NFS/EFS/CephFS 等网络存储；改用块存储 StorageClass |
| Pod 报 `secret "openassassin-secrets" not found` 或 `couldn't find key ...` | 未创建 Secret 或缺键，按第 2 步创建四个键 |
| backend CrashLoopBackOff，日志提示只读文件系统 | 确认 PVC 挂载在 `/app/data`；如仍失败，将 `readOnlyRootFilesystem` 改为 `false` |
| frontend CrashLoopBackOff | 检查 `backend` Service 是否存在；或先将 frontend 的 `readOnlyRootFilesystem` 改为 `false` |
| Ingress 404 | 检查域名是否已替换、`IngressClass/nginx` 是否存在 |
| 502 Bad Gateway | 后端未 Ready，或后端 Service 名被改动（必须叫 `backend`） |
| 脚本执行提示 `[SANDBOX_DISABLED]` | 预期行为，见第 8 节 |
| 升级后旧凭据无法解密 | `MASTER_KEY` 被更换，需恢复原 Secret |

## 10. 安全说明

- Secret 不进入 Git，也不由 Kustomize 管理；`k8s/secret.yaml` 已在 `.gitignore` 中。
- 后端不挂载 docker.sock、不 privileged、不 hostPath；drop ALL capabilities、
  只读根文件系统、`seccompProfile: RuntimeDefault`。
- 后端/前端 Service 均为 ClusterIP，唯一外部入口是 Ingress。
- `automountServiceAccountToken: false`，应用不需要访问 Kubernetes API。
- 生产环境务必启用 TLS，否则登录密码与 JWT 会以明文传输。
- `k8s/networkpolicy.yaml` 为可选最小网络策略，启用前确认 CNI 与 kubelet 探针兼容。
