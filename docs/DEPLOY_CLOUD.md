# Streamlit Cloud 部署更新说明

## 为什么 Reboot 后页面「没变」？

最常见原因：**GitHub 上的代码还是旧版本**。Cloud 只部署远程仓库，不会读你本机未推送的修改。

### 检查步骤

1. 本地执行：
   ```powershell
   git status
   git log origin/master -1 --oneline
   ```
   若 `git status` 有大量 `M` / `??`，或本地 `git log -1` **新于** `origin/master`，说明**还没 push**。

2. 推送后再部署：
   ```powershell
   git add -A
   git commit -m "你的说明"
   git push origin master
   ```

3. 打开 [share.streamlit.io](https://share.streamlit.io) → 你的 App → **Manage app** → **Reboot app**。

4. 打开网页，看侧边栏最底部版本号，例如：
   - `界面 2026.05.20-no-image-ocr` → 已移除图片识题，保留文字输入与四阶段流程

### 其它可能

| 现象 | 处理 |
|------|------|
| Cloud 绑错分支 | Settings 里确认 Branch 为 `master`（或你推送的分支） |
| 浏览器缓存 | 无痕窗口打开 App 链接 |
| Secrets 里旧 `LLM_MODEL` | 删掉 `deepseek-chat`，或留空让侧边栏选择 |
| 打开的不是这个 App | 确认 URL 对应 `application-writing-project1` 仓库 |

---

*Reboot 只会重新拉取 GitHub 上的最新提交，不会同步本机未 push 的文件。*
