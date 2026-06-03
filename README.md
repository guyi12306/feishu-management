# 飞书自动化智能体

一个 AI 智能体桌面 / Web 应用:**用自然语言描述需求 → 智能体编排成工作流 → 自建引擎调度执行(可选写飞书)。**

- 后端:Python 3.11+ / FastAPI / SQLite / APScheduler / cryptography(Fernet)
- 前端:Vue 3 / Vite / TypeScript / Tailwind / Vue Flow / Pinia
- LLM:OpenAI 兼容 API(走 base_url,可换 DeepSeek / Kimi / 通义 / 自部署)
- 飞书:`httpx` 直调 OpenAPI(`tenant_access_token` 缓存)

---

## 一句话流程

```
你说「每天 9 点把销售表近 24h 新增订单汇总发到运维群」
   ↓
Agent 调 list_bitables / list_chats / get_table_fields 看清现状
   ↓
Agent 调 create_draft 把工作流写进草稿箱(对话里弹卡片)
   ↓
你点【进草稿箱编辑】→ 画布上微调 → 点【应用到飞书】
   ↓
后端 APScheduler 接管,按 cron 触发,真去查 / 真去发
```

> 飞书的「自动化」并没有公开 OpenAPI 让外部程序往里写规则,所以本项目走**方案 A**:
> 我们自建引擎(`engine/`),不依赖飞书内部自动化能力。

---

## 跑起来(Windows / PowerShell)

### 后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
copy .env.example .env       # 至少改 SESSION_SECRET
python -m app
# → http://127.0.0.1:8000
```

### 前端

```powershell
cd web
npm install
npm run dev
# → http://localhost:5173
```

打开浏览器 → 用 **admin / admin123** 登录(首次启动后端会自动建)。

> ⚠️ 登录后第一件事:进【设置】改密。

### 配凭证

设置页两块凭证,加密落库(Fernet + PBKDF2 from `SESSION_SECRET`):

1. **LLM**(必填,否则对话走 Mock)
   - Base URL / 模型 / API Key
   - 「测试连接」会发一次最小请求验证
2. **飞书**(选填,只有真要查表/发消息才需要)
   - 自建应用的 App ID + App Secret
   - 需要的权限:`bitable:app:readonly` / `im:message:send_as_bot` / `im:chat:readonly`
   - 「测试连接」会拿一次 `tenant_access_token`

---

## 工程结构

```
飞书管理/
├── PLAN.md                       方案与决策记录
├── README.md                     本文档
├── backend/
│   ├── pyproject.toml
│   ├── .env.example
│   └── app/
│       ├── main.py               FastAPI 入口
│       ├── config.py / db.py     配置 + SQLite schema
│       ├── security.py           bcrypt + Fernet + Session
│       ├── secrets_store.py      加密键值
│       ├── lark_client.py        飞书 httpx 客户端
│       ├── api/                  路由
│       │   ├── auth.py
│       │   ├── chat.py           /api/chat /api/chat/stream
│       │   ├── workflows.py      草稿 CRUD + apply/unapply/run-now
│       │   └── settings.py
│       ├── agent/                智能体
│       │   ├── core.py           Function Calling 主循环
│       │   ├── llm.py            OpenAI 兼容客户端 + SSE
│       │   ├── prompts.py
│       │   └── tools/            list_bitables / list_chats / create_draft 等
│       └── engine/               自建工作流引擎
│           ├── scheduler.py      APScheduler 包装
│           └── executor.py       拓扑序节点执行
└── web/
    ├── package.json
    ├── tailwind.config.ts        玻璃风设计系统
    └── src/
        ├── views/                Login / Chat / Workflows / Settings
        ├── components/
        │   ├── chat/             消息气泡 / 草稿卡 / ToolCallChip
        │   ├── workflow/         画布 / 节点 / Inspector / RunsDrawer
        │   ├── layout/           AppShell + SideBar
        │   └── ui/               GlassPanel / Button / Toast
        ├── stores/               pinia
        └── api/                  axios 封装
```

---

## 节点能力

| 节点 | 配置字段 | 输出 |
|---|---|---|
| `trigger.schedule` | `cron, tz` | `triggered_at` |
| `trigger.bitable_change` | `app_token, table_id, event` | (Phase 5 webhook) |
| `action.bitable_query` | `app_token, table_id, filter?` | `records, count` |
| `action.send_message` | `chat_id, template` | `message_id, sent_text` |
| `action.http` | `method, url, body?` | `status, body` |
| `condition.if` | `expression` | `passed`(为假时下游全跳过) |

字段值里可以用模板变量 `{{nodes.a1.count}}` / `{{trigger.payload.id}}`,执行时按上下文求值。

---

## 已知边界 / 后续

- `trigger.bitable_change` 需要飞书 webhook 接收端点,目前仅作为节点占位,实际触发未启用。
- Agent 历史目前不做摘要,长对话超出 LLM context 会出问题(>30 条会被截断保留最近 30 条)。
- 画布 condition.if 的分支只支持「真往下 / 假截断」,不支持双分支(yes/no 两条线)。
- 没用任何外部状态服务;APScheduler 用 MemoryJobStore,重启时通过 `restore_all()` 从 DB 重建 job。

---

## 默认账号 / 端口

| 项 | 值 |
|---|---|
| 后端 | http://127.0.0.1:8000 |
| 前端 | http://localhost:5173 |
| 默认账号 | admin / admin123 |
| 数据库 | `backend/data/app.db` |

数据库和 `.env` 都在 `.gitignore` 里,不会进 git。
