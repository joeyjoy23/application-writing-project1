# Neon 云端历史配置指南

网页版（Streamlit Cloud）重启后历史不丢，且**普通用户只看自己的记录**；**管理员**可在侧边栏解锁后查看全部。

## 1. 注册 Neon

1. 打开 https://neon.tech 注册（免费档约 500MB）。
2. 新建 Project → 复制 **Connection string**（选 `Pooled` 或 `Direct` 均可，需带 `?sslmode=require`）。

示例：

```text
postgresql://user:password@ep-xxxx.region.aws.neon.tech/neondb?sslmode=require
```

## 2. 建表（可选）

应用首次启动会自动 `CREATE TABLE`。也可在 Neon **SQL Editor** 手动执行：

```sql
CREATE TABLE IF NOT EXISTS history (
    id BIGSERIAL PRIMARY KEY,
    owner_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    topic TEXT NOT NULL,
    model_name TEXT NOT NULL,
    full_content TEXT NOT NULL,
    word_count INTEGER NOT NULL DEFAULT 0,
    stages_mask CHAR(4) NOT NULL DEFAULT '0000',
    question_hash TEXT NOT NULL DEFAULT '',
    raw_input TEXT NOT NULL DEFAULT '',
    UNIQUE (owner_id, question_hash, model_name)
);
CREATE INDEX IF NOT EXISTS idx_history_owner_created ON history (owner_id, id DESC);
```

## 3. Streamlit Cloud Secrets

在应用 **Settings → Secrets** 添加：

```toml
DATABASE_URL = "postgresql://...."

ADMIN_PASSWORD = "你的管理员密码"

# 若希望网页默认用服务端 Key（可选）
DEEPSEEK_API_KEY = "sk-..."
LLM_PROVIDER = "deepseek"
LLM_MODEL = "deepseek-v4-pro"
```

保存后 **Reboot app**。

> **切勿**把 `DATABASE_URL` 或 `ADMIN_PASSWORD` 提交到 GitHub。

## 4. 本地开发

在项目根目录 `.env` 中配置同上；留空 `DATABASE_URL` 则继续使用本地 `history.db`。

## 5. 使用说明

| 角色 | 行为 |
|------|------|
| 普通访客 | 自动分配 `guest_id`，历史列表只显示自己的 |
| 管理员 | 侧边栏**最底部**空白处点击 → 输入 `ADMIN_PASSWORD` → 可查看/删除全部 |

换浏览器或清缓存会生成新的 `guest_id`，旧历史对该浏览器不可见（除非管理员查看）。

## 6. 故障排查

| 现象 | 处理 |
|------|------|
| 历史仍丢失 | 确认 Secrets 里 `DATABASE_URL` 正确且已 Reboot |
| 无法连接数据库 | 检查 Neon 项目是否休眠、连接串是否含 `sslmode=require` |
| 管理员无法解锁 | 确认 `ADMIN_PASSWORD` 与输入一致（仅存在于 Secrets） |
| 依赖安装失败 | 确保 `requirements.txt` 含 `psycopg[binary]` |
