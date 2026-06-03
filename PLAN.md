# Lark Automation Agent · 方案总览

> 📌 **本文档用于评审与对齐,获你确认后再开始大规模编码。**

---

## 1. 项目核心定位(一句话)

**一个 AI 智能体:用自然语言描述需求 → 智能体生成工作流草稿 → 用户在「草稿箱」里用可视化画布二次编辑 → 一键应用到飞书 / 我们自带的引擎。**

> 核心闭环 = **对话生成 + 可视化编辑 + 一键应用**。对话不是终点,画布编辑器才是。

---

## 2. 典型使用场景

### 场景 A:从零建一条自动化规则

```
用户:每天 9 点把销售表近 24 小时新增的订单汇总发到运维群
   ↓
[智能体]
  1. 解析意图 → 触发: schedule (每天 9 点)
                 动作: query Bitable + send message
  2. 查飞书可用资源:
     - 列你能访问的多维表格 → 找到「销售表」
     - 列你能发消息的群 → 找到「运维群」
  3. 生成工作流草稿(节点 + 连线 JSON + 自然语言描述)
  4. 在对话气泡里展示「草稿卡」,提供:
     [📋 进草稿箱编辑] [⚡ 直接应用] [✖️ 丢弃]
   ↓
[草稿箱 / 画布编辑器](独立路由 /workflows/{id})
  5. 用户在可视化画布里二次编辑:
     - 改触发器(cron 时间、Webhook、表变更等)
     - 增/删/改动作节点(查 Bitable、发消息、调 HTTP、跑脚本)
     - 拖连线、加条件分支
     - 改字段映射、消息模板(Markdown)
  6. 【保存草稿】写入我们 DB,可随时回来继续改
  7. 【应用到飞书】才真调 OpenAPI 写飞书(或走我们自己的引擎)
  8. 返回确认 + 飞书内跳转链接(若飞书侧创建成功)
```

### 场景 B:管理已有的自动化规则

```
用户:看看销售表上现在有哪些自动化在跑?
   ↓
[智能体]
  - 调 OpenAPI 列出该表的自动化
  - 卡片化展示(触发/动作/启停状态)
  - 用户可以点【暂停/重启/删除】,或【拉到草稿箱二次编辑】
```

### 场景 C:自然语言查询/操作

```
用户:把刚才那个早报改成每天 10 点
[智能体] → 找到对应草稿 → 改 cron 节点 → 重新应用
        (或直接打开画布让用户自己改)
```

### 场景 D:草稿箱直接新建 / 维护

```
用户进「工作流」→ 新建空白工作流 / 复制已有 / 改 / 应用
不经对话,直接在画布上拖。
（适合熟练用户、模板复用、跨对话的工作流维护)
```

---

## 3. 整体架构

```
┌──────────────────────────────────────────────────┐
│                    前端 (Web SPA)                  │
│  Vue 3 + Vite + Tailwind  · 玻璃拟物风             │
│  ├─ 登录页                                         │
│  ├─ 对话主页(会话列表 + 消息流 + 输入框)         │
│  ├─ 工作流(草稿箱列表 + 画布编辑器 Vue Flow) ★   │
│  ├─ 设置页(LLM / 飞书凭证 / 改密)                │
│  └─ 已应用规则列表(可选,后期)                    │
└────────────────────────┬─────────────────────────┘
                         │ HTTPS (axios)
┌────────────────────────┴─────────────────────────┐
│                    后端 (FastAPI)                  │
│  ├─ /api/auth       登录态                         │
│  ├─ /api/chat       发消息 → 跑 Agent              │
│  ├─ /api/conversations  会话管理                   │
│  └─ /api/settings    配置                          │
└──┬──────────────────┬────────────────────────────┘
   │                  │
┌──┴────────────────┐  ┌──┴───────────────────────┐
│  SQLite           │  │         Agent 核心         │
│ users             │  │  ┌────────────────────┐   │
│ conversations     │  │  │  LLM (OpenAI 兼容) │   │
│ messages          │  │  └────────────────────┘   │
│ workflow_drafts ★ │  │           ↓ tool_call      │
└─────────┬─────────┘  │  ┌────────────────────┐   │
          │            │  │      Tools           │  │
          │            │  │  只读探查:            │  │
          │            │  │  • list_bitables     │  │
          │            │  │  • list_tables       │  │
          │            │  │  • get_table_fields  │  │
          │            │  │  • list_chats        │  │
          │            │  │  草稿写入(主入口):     │  │
          │            │  │  • create_draft  ★   │  │
          │            │  │  • update_draft  ★   │  │
          │            │  │  应用层(用户点应用才走):│  │
          │            │  │  • apply_draft   ★   │  │
          │            │  │  • list_automations  │  │
          │            │  │  • delete_automation │  │
          │            │  └────────────────────┘   │
          │            │           ↓                │
          │            │  ┌────────────────────┐   │
          │            │  │ 飞书 API 调用层      │   │
          │            │  │ • httpx OpenAPI    │   │
          │            │  │ • OR Lark CLI      │   │
          │            │  └────────────────────┘   │
          │            └──────────┬─────────────────┘
          │                       ↓
          │             飞书 OpenAPI / 多维表格
          │
          │            ┌────────────────────────┐
          └───────────→│ Workflow Engine ★      │
                       │ (方案 A 后备:我们自跑) │
                       │ • APScheduler 定时     │
                       │ • Runner 执行节点图     │
                       │ • 失败重试 / 日志       │
                       └────────────────────────┘
```

> ★ = 本轮新增,围绕「**工作流草稿箱 + 可视化编辑**」这条主线。

---

## 4. 技术栈

| 层 | 选择 | 理由 |
|---|---|---|
| **后端语言** | Python 3.11+ | 你熟、生态全、httpx/openai/FastAPI 顺手 |
| **后端框架** | FastAPI | 异步 + Pydantic + 自带 docs |
| **数据库** | SQLite | 零部署、单文件,够这一阶段 |
| **认证** | Cookie session(itsdangerous 签名) | 简单可靠 |
| **LLM** | OpenAI 兼容 API | 通过 base_url 适配 OpenAI/DeepSeek/Kimi/通义/自部署 |
| **飞书 SDK** | `httpx` 直调 OpenAPI(主) + Lark CLI 子进程(次) | 直接 API 比 CLI 更可控;Lark CLI 备用 |
| **前端框架** | Vue 3 + Vite + TypeScript | 你熟 |
| **样式** | **Tailwind CSS**(不用 Element Plus) | 玻璃拟物风需要细节控制,EP 不易改 |
| **组件** | Headless UI + 自建 | 只要 accessibility,样式 100% 自控 |
| **图标** | Lucide Vue | 线性、克制、统一 |
| **状态** | Pinia | Vue 标配 |
| **路由** | Vue Router | 同上 |
| **画布 ★** | `@vue-flow/core` + `@vue-flow/background` + `@vue-flow/controls` | 节点拖拽 / 连线 / 缩放都给你;节点模板用 Vue SFC 自渲染 → 玻璃风可控 |
| **JSON Schema 表单 ★** | 自建轻量(节点 inspector 用)| 节点配置面板按字段类型渲染输入,避免引重型库 |
| **调度 ★** | APScheduler(后备引擎用) | 纯 Python,无需 Redis;单机够用 |

---

## 5. 设计系统(深海青金 · 仅浅色)

### 颜色

| 用途 | 值 |
|---|---|
| **背景渐变** | `linear-gradient` + 多层 `radial-gradient`<br>主色:`#F0F7F9 → #ECF1F5 → #EEEDF0`<br>顶部点缀冷青/淡薰衣草色斑 (`#A5C7D6` / `#C4A1D7`,opacity 0.18) |
| **品牌色 / CTA** | `#4F46E5`(混紫蓝,"青") |
| **点缀金** | `#D4A056`(暗金,极少量用于装饰/高亮)("金") |
| **文字主色** | `#0F1419` |
| **文字次色** | `#6B7280` |
| **辅助文字** | `#9CA3AF` |
| **成功 / 失败** | `#10B981` / `#EF4444`(克制使用) |

### 玻璃面

| 层级 | 规格 |
|---|---|
| **常规玻璃**(主卡片、侧栏) | `bg-white/55` + `backdrop-blur(24px) saturate(180%)` + `border 1px white/70` + 双层阴影 + 顶部 1px inset 高光 |
| **强玻璃**(浮层、Dialog) | `bg-white/65` + `backdrop-blur(32px)` + `border 1px white/80` + 更深阴影 |
| **平面元素**(按钮、输入框) | **不用** blur,纯色 `bg-white/70` |

### 字体层级

| 级别 | 大小 | 字重 | 字距 | 用途 |
|---|---|---|---|---|
| Display | 28-32px | 600 | -0.02em | 页面大标题 |
| Title | 18-20px | 600 | -0.01em | 卡片标题 |
| Body | 14-15px | 400 | 0 | 正文 |
| Caption | 12-13px | 400 | 0 | 辅助、时间戳 |

字体栈:`-apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif`

### 间距系统

`4 / 8 / 12 / 16 / 24 / 32 / 48 / 64`

### 圆角

`8 / 12 / 16` 三档,按"按钮 / 卡片 / 大面板"递增。

### 阴影

```css
/* 玻璃常规 */
0 8px 32px rgba(15, 20, 25, 0.04),
0 1px 0 rgba(255, 255, 255, 0.6) inset

/* 玻璃强 */
0 24px 48px rgba(15, 20, 25, 0.08),
0 1px 0 rgba(255, 255, 255, 0.8) inset
```

### 动效

只在"状态切换"用,`200-300ms` `cubic-bezier(0.4, 0, 0.2, 1)`,不抢戏。

---

## 6. 目录结构

```
飞书管理/
├── README.md                       项目说明
├── PLAN.md                         本文档
├── .gitignore
│
├── backend/                        后端
│   ├── pyproject.toml
│   ├── .env.example
│   └── app/
│       ├── __init__.py
│       ├── __main__.py             启动入口
│       ├── main.py                 FastAPI 实例
│       ├── config.py               配置
│       ├── db.py                   SQLite 接口
│       ├── security.py             密码 / Session
│       ├── auth.py                 认证业务
│       ├── api/                    路由
│       │   ├── auth.py             /api/login /me /change-password
│       │   ├── chat.py             /api/chat /conversations
│       │   ├── workflows.py    ★   /api/workflows CRUD + apply
│       │   └── settings.py         /api/settings
│       ├── agent/                  智能体核心
│       │   ├── core.py             ReAct 主循环
│       │   ├── llm.py              OpenAI 客户端
│       │   ├── prompts.py          System Prompt 模板
│       │   └── tools/              工具集
│       │       ├── base.py         Tool 基类
│       │       ├── bitable.py      多维表格相关
│       │       ├── chat.py         飞书消息/群
│       │       ├── workflow.py ★   create_draft / update_draft / apply_draft
│       │       └── automation.py   规则反查(list / delete 已应用的)
│       ├── workflow/           ★   工作流模型 & 引擎
│       │   ├── schema.py           节点/边类型定义、JSON Schema 校验
│       │   ├── nodes.py            节点定义注册表(trigger/action/condition)
│       │   ├── compiler.py         draft graph → 飞书规则 JSON / 引擎计划
│       │   └── engine/             方案 A 自跑引擎
│       │       ├── scheduler.py    APScheduler 包装
│       │       ├── runner.py       节点遍历执行器
│       │       └── log.py          运行日志
│       └── lark_client.py          httpx 封装,token 缓存
│
└── web/                            前端
    ├── package.json
    ├── vite.config.ts
    ├── tailwind.config.ts
    ├── postcss.config.js
    ├── tsconfig.json
    ├── index.html
    └── src/
        ├── main.ts
        ├── App.vue
        ├── style.css               Tailwind + 自定义工具类
        ├── router/index.ts
        ├── api/
        │   ├── client.ts           axios 实例
        │   ├── auth.ts
        │   ├── chat.ts
        │   ├── conversations.ts
        │   └── workflows.ts    ★   草稿 CRUD / apply
        ├── stores/
        │   ├── auth.ts
        │   ├── chat.ts
        │   ├── workflows.ts    ★   草稿列表 + 当前编辑中的草稿
        │   └── settings.ts
        ├── components/
        │   ├── ui/                 通用原语
        │   │   ├── Button.vue
        │   │   ├── Card.vue
        │   │   ├── Input.vue
        │   │   └── GlassPanel.vue
        │   ├── chat/
        │   │   ├── MessageBubble.vue        消息气泡(用户/助手)
        │   │   ├── DraftCard.vue        ★   草稿卡(代替 AutomationCard)
        │   │   ├── ToolCallChip.vue         工具调用记录(可折叠)
        │   │   ├── ChatInput.vue            输入框 + 发送
        │   │   └── ConversationList.vue     左侧会话列表
        │   ├── workflow/        ★          可视化编排
        │   │   ├── Canvas.vue                Vue Flow 主画布
        │   │   ├── NodePalette.vue           左侧节点抽屉(可拖入)
        │   │   ├── Inspector.vue             右侧节点配置面板
        │   │   ├── Toolbar.vue               顶部工具条(保存/应用/撤销)
        │   │   ├── DraftList.vue             草稿箱列表
        │   │   └── nodes/                    每种节点的渲染组件
        │   │       ├── TriggerNode.vue
        │   │       ├── ActionNode.vue
        │   │       └── ConditionNode.vue
        │   └── layout/
        │       ├── AppShell.vue             主壳(背景 + 容器)
        │       └── SideBar.vue              侧栏(对话/工作流/设置)
        └── views/
            ├── Login.vue                    登录页
            ├── Chat.vue                     对话主页
            ├── Workflows/               ★   工作流模块
            │   ├── Index.vue                 /workflows  草稿箱列表
            │   └── Editor.vue                /workflows/:id 画布编辑器
            ├── Settings.vue                 设置页
            └── (Automations.vue)            已应用规则列表(可选)
```

---

## 7. 功能分阶段

### 🎨 Phase 1 — 视觉基础与对话壳 (~ 1 天)

> **目标:UI 立起来,壳和样式都跑通。不接 LLM,后端用 mock 响应。**

- 项目骨架(前后端)
- Tailwind 玻璃设计系统(背景渐变 + glass utility + 字体层级)
- 登录页:玻璃登录卡 / 居中 / 渐变背景
- 主壳:左侧栏(对话 / **工作流** / 设置 三个一级导航)+ 主区
- 消息气泡(用户右,助手左)
- 草稿卡(DraftCard,在消息流里展示智能体生成的工作流摘要 + 三按钮)
- 后端:登录 / 当前用户 / mock chat 接口
- 浏览器联调,看效果

### 🤖 Phase 2 — 接入 LLM,真智能 (~ 1-1.5 天)

> **目标:聊天真的会调 LLM,但工具暂时只读(不写飞书)。**

- LLM 客户端封装(OpenAI 兼容)
- Agent 主循环(Function Calling 协议)
- System Prompt(描述任务、工具列表、输出格式)
- 工具(只读):`list_bitables`、`list_tables`、`list_chats`、`get_table_fields`
- 流式响应(SSE)
- 前端流式渲染(逐字显示)
- 工具调用过程可视化(可折叠的 tool call chip)

### 🧩 Phase 3 — 草稿箱 + 可视化画布(本轮主战场)(~ 1.5 天) ★

> **目标:工作流从对话生成 → 进入草稿箱 → 可视化编辑 → 保存,完整闭环;但还没写飞书。**

- 数据层:`workflow_drafts` 表 + 节点 JSON Schema(`workflow/schema.py`)
- API:`/api/workflows` CRUD + `/from-message`(把消息里的草稿吃进草稿箱)
- Agent 工具:`create_draft` / `update_draft` —— Agent 不再直接写飞书,只生成草稿
- 前端:
  - 草稿箱列表页(`/workflows`):卡片网格 + 搜索 + 状态筛选(draft/applied/archived)
  - 画布编辑器页(`/workflows/:id`):
    - 顶部 Toolbar:草稿名、保存、应用、撤销/重做
    - 左侧 NodePalette:触发器 / 动作 / 条件 三类节点,可拖入画布
    - 中央 Canvas(Vue Flow):节点 + 连线,自定义玻璃风节点
    - 右侧 Inspector:选中节点 → 按 schema 渲染配置表单
  - 对话气泡里的 DraftCard 点【📋 进草稿箱编辑】→ 跳到 `/workflows/:id`
- 自动保存(防丢)+ 显式【保存草稿】按钮

### ⚡ Phase 4 — 应用层:写飞书 / 我们引擎 (~ 1 天)

> **目标:草稿点【应用】真的能跑起来。**

- Phase 4.0(开工前 30 分钟):验证飞书自动化 OpenAPI 是否可用(见 §10.1)
- 应用工具:`apply_draft` / `unapply_draft` / `list_applied`
- `workflow/compiler.py`:把节点图编译成
  - 飞书 OpenAPI 调用序列(若 API 可用)
  - 或者我们引擎的执行计划(方案 A)
- 我们引擎(若需):APScheduler + Runner 跑节点图
- 失败回滚 + 详细错误提示
- 草稿状态机:draft → applied,记 `applied_target`(飞书 rule id 或引擎 rule id)

### 🔧 Phase 5 — 细节打磨 (~ 0.5-1 天)

- 设置页:LLM Key / 飞书凭证(secrets 加密存)/ 改密
- 历史会话列表 + 重命名 + 删除
- 草稿模板复制 / 导出 JSON / 导入 JSON
- 错误边界、loading 状态、网络重连
- 移动端响应式(可选)

**总工期估算:4.5 - 6 天**(Phase 3 画布是新增的重头,实际开工后会更准)

---

## 8. 数据模型

核心 4 张表:

```sql
-- 用户
users (
  id, username, password_hash, display_name,
  created_at, last_login_at
)

-- 会话(一次完整对话)
conversations (
  id, user_id, title,
  created_at, updated_at
)

-- 消息(用户 / 助手 / 工具)
messages (
  id, conversation_id,
  role,             -- user | assistant | tool
  content,          -- 文本
  tool_calls,       -- JSON,助手发起的工具调用
  tool_result,      -- JSON,工具返回(role=tool 时)
  draft_id,     ★   -- 关联到生成的工作流草稿(可空)
  created_at
)

-- 工作流草稿 ★
workflow_drafts (
  id, user_id,
  name,             -- 草稿名(用户可改)
  description,      -- 一句话描述(智能体生成,可改)
  graph,            -- JSON: { nodes: [...], edges: [...], viewport: {...} }
                    --   nodes[i] = { id, type, position, config }
                    --   type ∈ trigger.schedule | trigger.webhook | trigger.bitable_change
                    --        | action.bitable_query | action.send_message | action.http
                    --        | condition.if
  status,           -- draft | applied | archived
  applied_target,   -- JSON: { kind: "feishu" | "engine", external_id, applied_at }
                    --   kind=feishu → 飞书规则 id;kind=engine → 我们引擎 rule id
  source_conversation_id,  -- 由哪个对话生成(NULL = 手动新建)
  source_message_id,       -- 具体哪条助手消息(NULL = 手动)
  created_at, updated_at, last_applied_at,
  FOREIGN KEY (user_id) REFERENCES users(id)
)
```

后期(Phase 5)可能加:
- `secrets`(加密存 LLM key / 飞书凭证)
- `workflow_runs`(若启用我们引擎,记每次跑的日志)

---

## 9. API 设计

| 端点 | 方法 | 用途 |
|---|---|---|
| `/api/login` | POST | 登录 |
| `/api/logout` | POST | 登出 |
| `/api/me` | GET | 当前用户 |
| `/api/change-password` | POST | 改密 |
| `/api/conversations` | GET | 会话列表 |
| `/api/conversations` | POST | 新建会话 |
| `/api/conversations/{id}` | GET | 会话详情(含所有消息) |
| `/api/conversations/{id}` | DELETE | 删除会话 |
| `/api/chat` | POST | 发消息 → Agent 处理 → 返回助手响应 |
| `/api/chat/stream` | POST(SSE) | 流式版本(Phase 2 加) |
| `/api/settings/llm` | GET/POST | LLM 配置 |
| `/api/settings/feishu` | GET/POST | 飞书凭证 |
| **工作流(★ 本轮新增)** | | |
| `/api/workflows` | GET | 草稿箱列表(支持 ?status=draft\|applied\|archived) |
| `/api/workflows` | POST | 新建空白草稿(用户在画布主动建) |
| `/api/workflows/from-message` | POST | 把 message.draft 拷贝/绑定到草稿箱(Agent 生成后调用) |
| `/api/workflows/{id}` | GET | 草稿详情(含完整 graph) |
| `/api/workflows/{id}` | PUT | 更新草稿(graph / name / description) |
| `/api/workflows/{id}` | DELETE | 删除草稿 |
| `/api/workflows/{id}/apply` | POST | 应用到飞书(或我们引擎),状态转 applied |
| `/api/workflows/{id}/unapply` | POST | 撤销应用(关闭已运行的) |
| `/api/workflows/{id}/duplicate` | POST | 复制草稿(模板复用用) |
| `/api/workflows/node-types` | GET | 当前支持的节点类型 + schema(画布初始化用) |

---

## 10. 关键技术点

### 10.1 飞书自动化规则的 OpenAPI 是否支持?

> ⚠️ **这是最大的风险点,需要落地后验证。**

我做过初步搜索,飞书 OpenAPI 的「**多维表格自动化**」相关接口:

- ✅ 多维表格 CRUD、记录 CRUD、字段 CRUD 都有
- ⚠️ "自动化工作流" 节点级别的创建 API 文档**不明显**(可能只在企业内部 / Aily 开放)
- ⚠️ 飞书产品里那个"自动化"是 Bitable 内嵌功能,不一定有公开的程序化 API

**降级策略**(若 OpenAPI 不支持):

| 方案 | 描述 |
|---|---|
| **A. 我们造一个引擎** | 不依赖 Bitable 内部自动化,我们后端跑 cron + 调 OpenAPI 执行;规则存我们 DB |
| **B. 输出导入文件** | Agent 生成 JSON,用户复制到 Bitable 自动化编辑器内导入(看 Bitable 支不支持导入) |
| **C. 用 Lark CLI 自动操作** | 通过 CLI 可能能模拟操作(不太确定) |

我推荐 **方案 A** 作为后备:即"我们造引擎"。这样不受飞书 API 限制,Agent 生成的规则我们自己跑。

**这件事我会在 Phase 3 第一件事就验证。** 如果飞书有公开 API 最好直接用;没有的话切方案 A,这个切换对前端透明。

### 10.2 Agent 协议:ReAct vs Function Calling

推荐用 **OpenAI Function Calling 协议**(其他 LLM 也大多兼容):
- LLM 输出 `tool_calls` 数组
- 我们执行后回 `role=tool` 消息
- LLM 继续推理
- 直到无新工具调用 → 返回最终响应

比 ReAct 更结构化、更稳。

### 10.3 流式响应

Phase 2 加 SSE。Phase 1 先同步返回(简单)。

### 10.4 工具实现策略

每个工具是一个 Python 函数 + JSON schema:

```python
TOOL_LIST_BITABLES = {
    "name": "list_bitables",
    "description": "列出当前用户能访问的所有多维表格",
    "parameters": {"type": "object", "properties": {}}
}

async def list_bitables() -> list[dict]:
    # 调飞书 API
    ...
```

工具按职能分文件:`bitable.py` / `chat.py` / `automation.py`。

### 10.5 Lark CLI 在哪里用?

**主要靠 httpx 直调 OpenAPI**(更可控、更快、不依赖 CLI 安装)。

**Lark CLI 作为补充**(可选):
- 当某些复杂操作 OpenAPI 不直接支持,但 CLI 能办
- 比如 Aily 助理调用、特殊 skill 等
- 用 subprocess 调

### 10.6 可视化编排画布 ★

#### 库选择:Vue Flow

| 候选 | 优点 | 缺点 |
|---|---|---|
| **Vue Flow**(推荐)| 节点 100% Vue SFC 自渲染 → 玻璃风可控;有 background / minimap / controls 子包;社区活;TS 完善 | 高级 layout 要自己写 |
| Drawflow | 体积小 | 节点 DOM 不太好定制,样式难贴齐玻璃风 |
| n8n-editor 拆出来 | 功能最全 | 体积大、AGPL 协议 |
| 自己撸 | 最自由 | 时间黑洞 |

#### 节点协议

每个节点遵守统一形态:

```ts
type WorkflowNode = {
  id: string;
  type: string;        // "trigger.schedule" | "action.send_message" | ...
  position: { x: number; y: number };
  config: Record<string, unknown>;  // 跟 schema 走,内容随 type 变
}

type WorkflowEdge = {
  id: string;
  source: string;      // node id
  target: string;
  label?: string;      // 条件分支用 ("yes" / "no")
}
```

后端 `workflow/nodes.py` 用注册表式登记每种节点 + 它的 JSON Schema:

```python
NODES = {
  "trigger.schedule": NodeSpec(
    label="定时触发",
    category="trigger",
    schema={ "cron": {"type": "string"}, "tz": {"type": "string"} },
  ),
  "action.send_message": NodeSpec(
    label="发送消息",
    category="action",
    schema={
      "chat_id": {"type": "string"},
      "template": {"type": "string", "format": "markdown"},
    },
  ),
  # ...
}
```

前端调 `/api/workflows/node-types` 拿这份注册表 → 渲染 NodePalette + Inspector 表单。
**新增节点只改后端这一个文件,前端零改动**。

#### MVP 节点种类(Phase 3 内交付)

- 触发:`trigger.schedule`(cron)、`trigger.bitable_change`(表变更)
- 动作:`action.bitable_query`、`action.send_message`(群/私聊)、`action.http`(发 HTTP)
- 条件:`condition.if`(简单字段比较)

更复杂的(循环、并行、子工作流)留到后续 Phase。

#### 编辑器交互

- 自动布局:不上,初版让用户自己拖。后续可以加一键整理(用 dagre)。
- 自动保存:debounce 800ms,本地 localStorage + 远端 PUT
- 校验:保存时跑一遍图校验(必须有 trigger / 不能有孤立节点 / config 必填项齐 / 没有环路)→ 不通过给详细错误,但允许保存(applied 时再强校验)
- 撤销/重做:基于 graph snapshot 栈,最近 50 步

---

## 11. 风险与未决问题

| 风险/问题 | 严重度 | 应对 |
|---|---|---|
| **飞书自动化规则没有公开 OpenAPI** | 🔴 高 | 切方案 A(我们造引擎);因为统一过 draft → apply,前端零感知 |
| **画布编辑器范围易膨胀** ★ | 🔴 高 | MVP 节点种类卡死在 §10.6 列表,自动布局/并行/子工作流明确推迟。Phase 3 单独看进度,超 1.5 天预警 |
| LLM API Key / 飞书凭证泄漏 | 🟡 中 | 加密存储(cryptography Fernet) |
| Agent 工具调用错误 / 死循环 | 🟡 中 | 最大轮次限制 + 工具调用超时 |
| 中文环境 + Windows 路径编码 | 🟢 低 | 我们之前已经踩过,有经验 |
| 长对话 token 爆炸 | 🟡 中 | 历史摘要 + 最近 N 轮 |
| 玻璃风在 Windows Chrome 老版本下表现差 | 🟢 低 | backdrop-filter 兼容性 95%+,可降级 |
| Vue Flow 节点样式与玻璃风冲突 | 🟢 低 | Vue Flow 节点完全自渲染,样式 100% 我们写,不冲突 |
| 节点 schema 改动破坏老草稿 | 🟡 中 | schema 加 `version`,加载老草稿时做 migration;不删字段只标 deprecated |

---

## 12. 当前已写代码(可保留 / 可删)

我刚才在你说停之前已经写了一部分**后端骨架**:

```
backend/
├── pyproject.toml         (已写)
├── .env.example           (已写)
└── app/
    ├── __init__.py        (已写)
    ├── __main__.py        (已写)
    ├── config.py          (已写,Pydantic Settings)
    ├── db.py              (已写,SQLite + schema)
    ├── security.py        (已写,密码哈希 + Session)
    ├── auth.py            (已写,登录业务)
    └── api/
        ├── auth.py        (已写,登录路由)
        └── chat.py        (已写,mock chat 路由)

README.md                  (已写)
.gitignore                 (已写)
```

**还差**:
- `backend/app/main.py`(FastAPI 实例)
- 前端整个 `web/` 目录
- 各种 Agent 相关文件(留到 Phase 2)

**你可以选**:
- 保留这部分代码(它符合上面的方案)
- 全部删掉重来

---

## 13. 需要你拍板的事

| # | 决策点 | 选项 |
|---|---|---|
| **A** | 总体方案是否 OK?| ✅ OK,继续 / ❌ 哪儿不对说一下 |
| **B** | 分阶段节奏是否 OK? | Phase 1(UI 壳)→ Phase 2(LLM)→ **Phase 3(草稿箱+画布)**→ Phase 4(写飞书+引擎)→ Phase 5(打磨) |
| **C** | 飞书自动化规则没有公开 API 时,切到「我们造引擎」可以接受吗? | 接受 / 不接受(改用 B 方案"输出导入文件") |
| **D** | 已写的后端骨架代码:保留还是删? | 保留 / 删 |
| **E** | 立刻可填的凭证 | LLM:模型 + Key 准备好了吗?<br>飞书:之前那对 App ID/Secret 还能用?需要重申请? |
| **F ★** | 画布 MVP 节点种类是否够? | §10.6 列出的 6 种:够 / 想加什么 |
| **G ★** | 草稿箱是否需要"模板库"(预置常用工作流)? | Phase 3 就要 / 留 Phase 5 / 不要 |
| **H ★** | 智能体生成的草稿默认应该 | 直接进草稿箱(用户主动打开)/ 在对话里展示卡片,用户选择是否进草稿箱(默认这个) |

---

## 14. 下一步(你确认后会做什么)

```
你说"OK,开始"
    ↓
Phase 1.1  写 backend/app/main.py(挂路由 + 启动)
Phase 1.2  初始化 web/ (Vite + Vue + Tailwind + TS)
Phase 1.3  配 Tailwind(玻璃工具类 + 色板 + 字体)
Phase 1.4  写公共组件(GlassPanel / Button / Card / Input)
Phase 1.5  登录页
Phase 1.6  AppShell + 三栏导航(对话 / 工作流 / 设置)
Phase 1.7  Chat 主壳 + 消息流(mock 数据)+ DraftCard(mock)
Phase 1.8  Workflows 列表页 + 编辑器页占位(mock)
Phase 1.9  联调,浏览器看效果
    ↓
拿给你看,确认设计感对不对
    ↓
进 Phase 2(LLM)→ Phase 3(草稿箱+画布,本轮核心)→ Phase 4(写飞书)→ Phase 5(打磨)
```

---

## 文档版本

- v1 · 2026-05-25 · 初版,等你审
- **v2 · 2026-05-25 · 引入「工作流草稿箱 + 可视化画布」主线**
  - 场景 A 流程改为:对话生成草稿 → 草稿箱画布编辑 → 显式 apply
  - 加 `workflow_drafts` 表、`/api/workflows` API、Vue Flow 画布
  - Phase 重排为 5 个,加 Phase 3(画布,本轮重头)
  - 工期 3.5–4.5 天 → 4.5–6 天
  - 新增决策项 F / G / H
