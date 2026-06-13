# API 设置拆分 + 浏览器记住 Key — 设计说明

**日期：** 2026-06-13  
**状态：** 已确认（方案 B + localStorage 方案 1）

## 目标

1. 侧边栏 **常用项在外**：模型提供商、模型选择、运行中停止。  
2. **敏感/运维项进「高级」**：API Key、LLM 缓存开关、运行日志。  
3. **可选「在本浏览器记住 Key」**：默认关闭，写入 `localStorage`；提供清除入口。

## 非目标

- 服务端按 guest_id 存 Key（不做）。  
- 用户口令加密 Key（不做，方案 2）。  
- 改变 `resolve_api_key()` 优先级（仍为：侧边栏 Key > Secrets/.env）。

## UI 结构

```text
侧边栏
├── 模式
├── 模型（外置）
│   ├── 提供商 selectbox
│   ├── 模型 selectbox
│   ├── 运行中 → 停止按钮
│   └── 状态：API 已配置 / 未配置（一行 caption）
├── 已生成内容索引
└── ⚙️ 高级 [API 未配置时自动展开]
    ├── API Key（password）
    ├── ☐ 使用 LLM 结果缓存
    ├── ☐ 在本浏览器记住 Key（默认关）
    ├── [清除本机已保存的 Key]
    └── 📋 运行日志
```

## 记住 Key 行为

| 操作 | 行为 |
|------|------|
| 勾选记住 + 填写 Key | 按 provider 写入 localStorage JSON |
| 取消勾选 | 删除 localStorage 中该 provider 的 Key |
| 清除按钮 | 删除全部已存 Key + 清空 session 中 manual key |
| 页面加载 | 若 remember 为 true 且当前 provider 有存 Key，填入 session（不覆盖用户本次已输入的非空值） |

**localStorage 键名：** `awp_api_keys_v1`  
**JSON 结构：** `{"remember": true, "keys": {"deepseek": "sk-...", ...}}`

## 安全

- 默认 **不勾选** 记住。  
- 勾选旁警告：勿在公共/共享电脑使用。  
- Key **不**写入历史、日志、导出、URL。  
- 清除本机 Key 一键可用。

## 依赖

- `streamlit-js-eval`：读写 localStorage（Streamlit 无内置回读）。

## 测试

- 单元：`services/api_key_persist.py` JSON 编解码。  
- E2E：展开高级、注入 session Key（localStorage 在 AppTest 中 mock/跳过）。
