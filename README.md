# Billbox

Billbox 是一个完全运行在自己机器上的私人账本：FastAPI 提供受保护的 API 和前端静态文件，后台定时读取招商银行账单邮件，SQLite 保存交易、原始邮件处理状态、修改审计和任务日志。React 页面使用 shadcn/ui，支持月度概览、筛选、手动记账和自动分类确认。

## 运行方式

仓库不在本机构建生产包。每次 push 到 `main` 后，GitHub Actions 只构建并推送多架构 Docker 镜像到 GHCR，不部署服务，也不创建 Git tag。镜像会提供两个容器标签：持续更新的 `main` 和对应提交的 `sha-xxxxxxx`。

1. 把仓库中的 `.env.example` 复制为 `.env`。
2. 将 `BILLBOX_IMAGE` 改成 Actions 生成的 `ghcr.io/<owner>/<repository>:main`。
3. 设置强密码，并用 `openssl rand -hex 32` 生成 `SESSION_SECRET`。
4. 如需邮件自动归集，填写 IMAP 配置。
5. 拉取并启动：

```bash
docker compose pull
docker compose up -d
```

GHCR 包若为私有，需要先用具备 `read:packages` 权限的 GitHub token 执行 `docker login ghcr.io`；也可以在 GitHub 包设置中将镜像改为公开。

默认只监听 `127.0.0.1:8000`。直接在本机打开 `http://127.0.0.1:8000` 即可。若通过 Nginx、Caddy 或其他反向代理提供 HTTPS，请把 `SESSION_COOKIE_SECURE` 改成 `true`，并将 `FORWARDED_ALLOW_IPS` 限制为反向代理的地址或网段。

更新服务：

```bash
docker compose pull
docker compose up -d
```

查看状态与日志：

```bash
docker compose ps
docker compose logs -f --tail=200 billbox
```

## 数据与备份

SQLite 数据库固定为 `/data/billbox.db`，由 Compose 的 `billbox-data` 命名卷持久化。容器启动时会自动按顺序应用 `migrations/` 中尚未执行的迁移。金额以整数分保存，交易性质与分类分离；邮件使用 IMAP UID 身份保证重复运行不会重复入账。

在线备份使用 SQLite Backup API，避免直接复制 WAL 状态中的数据库文件：

```bash
docker compose exec -T billbox python -c "import sqlite3; source=sqlite3.connect('/data/billbox.db'); backup=sqlite3.connect('/data/billbox.backup.db'); source.backup(backup); backup.close(); source.close()"
docker compose cp billbox:/data/billbox.backup.db ./billbox.backup.db
```

恢复前应先停止服务，并保留当前数据库副本。若改用宿主机 bind mount，目录必须允许容器内 UID/GID `10001:10001` 写入。

## 邮件自动归集

填写以下变量后，应用会按设定时区每天运行一次，也可以在页面中点击“立即抓取”：

- `MAIL_USER`、`MAIL_PASSWORD`：IMAP 登录信息；建议使用邮箱应用专用密码。
- `IMAP_SERVER`、`IMAP_PORT`：IMAP TLS 服务，默认端口 993。
- `MAX_EMAILS`：每轮最多检查的邮件数。
- `SCHEDULE_HOUR`、`SCHEDULE_MINUTE`、`SCHEDULE_TIMEZONE`：运行时间。

没有填写完整邮箱配置时，自动归集不会启动，但登录、查看和手动记账仍可使用。每轮抓取的状态、摘要和最近 20,000 字符日志都会写入 SQLite 并显示在页面中。

## 本地开发与检查

Python 使用 Conda 环境 `billbox`：

```bash
conda run -n billbox python -m pytest tests/backend -q
```

前端只需运行静态检查和开发服务器，不执行生产构建：

```bash
cd frontend
npm ci
npm test -- --run
npm run typecheck
npm run lint
npm run dev
```

Vite 开发服务器会把 `/api` 和 `/healthz` 代理到 `127.0.0.1:8000`。后端开发服务器需要设置 `APP_PASSWORD`、至少 32 字符的 `SESSION_SECRET`，并将 `SESSION_COOKIE_SECURE=false`。

## 安全边界

- 容器以非 root 用户运行、根文件系统只读，并移除 Linux capabilities。
- 登录 Cookie 为 HttpOnly、SameSite=Strict；写操作还要求会话内 CSRF token。
- 登录失败在进程内限流。服务重启会清空限流状态，因此仍应只在本机或可信反向代理后暴露。
- IMAP 仅使用系统信任链验证的 TLS，不跳过证书校验。
- 单容器固定一个 Uvicorn worker，确保 SQLite 写入、调度器与重入锁只有一个进程所有者。
