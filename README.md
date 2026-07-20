# Agent_001 — 扫地机器人多智能体协作系统

基于 **FastAPI + Vue 3 + LLM** 的全栈智能机器人系统，融合 **RAG（检索增强生成）**、**多智能体协作（Multi-Agent）**、**ReAct 决策循环** 与 **强化学习导航**，实现扫地机器人的智能控制、知识问答与自主任务规划。

---

## 🏗️ 系统架构

```
┌──────────────────────────────────────────────────────────────────────┐
│                          Frontend (Vue 3)                            │
│   Chat │ Knowledge Base │ Memory │ Mission Center │ Task History    │
│                     SSE / WebSocket / HTTP                           │
└──────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      FastAPI Application                             │
│                                                                      │
│  ┌──────────┐  ┌──────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │  REST    │  │  WebSocket   │  │  Lifecycle  │  │   System    │  │
│  │  /api/*  │  │  /ws/robot   │  │  startup/   │  │  Container  │  │
│  │          │  │              │  │  shutdown   │  │   (DI/IoC)  │  │
│  └──────────┘  └──────────────┘  └─────────────┘  └──────┬──────┘  │
│                                                           │         │
│  ┌────────────────────────────────────────────────────────┘         │
│  │                                                                    │
│  ▼                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    Multi-Agent System                         │   │
│  │                                                               │   │
│  │  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐      │   │
│  │  │ Supervisor   │   │  Perception  │   │  Navigation  │      │   │
│  │  │   Agent      │   │    Agent     │   │    Agent     │      │   │
│  │  │ (任务编排)    │   │ (传感器处理)  │   │ (路径规划)   │      │   │
│  │  └──────┬───────┘   └──────────────┘   └──────┬───────┘      │   │
│  │         │                                      │              │   │
│  │  ┌──────▼───────┐   ┌──────────────┐   ┌──────▼───────┐      │   │
│  │  │ ReAct        │   │  Execution   │   │ RL Navigation│      │   │
│  │  │ Runtime      │   │    Agent     │   │    Agent     │      │   │
│  │  │ (LLM 推理)   │   │ (速度/电源)   │   │ (强化学习)    │      │   │
│  │  └──────┬───────┘   └──────────────┘   └──────────────┘      │   │
│  │         │                                                      │   │
│  │  ┌──────▼──────────────────────────────────────────────┐      │   │
│  │  │              Tool Registry (14 tools)                 │      │   │
│  │  │  RoomQuery │ Coverage │ Knowledge │ Memory │ Calc   │      │   │
│  │  │  Weather │ Notify │ Confirm │ AskUser │ Planner     │      │   │
│  │  └─────────────────────────────────────────────────────┘      │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                   Infrastructure                              │   │
│  │  MessageBus │ EventRouter │ AgentRegistry │ ResourceManager  │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                      RAG System                               │   │
│  │  Query Routing → Query Rewriting → Vector Retrieval → LLM    │   │
│  │  ChromaDB │ Long-Term Memory │ Chat History │ ONNX Embedding │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                   LLM Layer                                   │   │
│  │  OpenAI / Claude / Gemini / DeepSeek / GLM / Qwen / 豆包 / 文心 ... │   │
│  │  兼容 15+ 云端模型及本地 Ollama 模型（工厂模式 + 统一 API 密钥管理）  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| **后端框架** | FastAPI | 异步 HTTP + WebSocket |
| **前端框架** | Vue 3 + Vite + Pinia | SPA with Element Plus UI |
| **LLM** | 本地 Ollama + 15+ 云端模型（OpenAI / Claude / Gemini / DeepSeek / GLM / 通义千问 / 豆包 / 文心 / 混元 / Moonshot / Yi / MiniMax / 百川 / Mistral / Grok 等） | 统一 API 密钥管理 + LLM 工厂模式 |
| **嵌入模型** | bge-m3 (ONNX 加速) | 文本向量化 |
| **向量数据库** | ChromaDB | 文档向量存储与语义检索 |
| **关系数据库** | MySQL + PyMySQL | 用户/聊天/知识库/任务持久化 |
| **消息通信** | 自研 MessageBus + EventRouter | Agent 间松耦合通信 |
| **强化学习** | SB3 PPO + RLConfig + RobotGymEnv | 365维观测、6项奖励、域随机化环境、混合控制 |
| **通信协议** | WebSocket + SSE (Server-Sent Events) | 实时状态推送 |
| **配置管理** | pydantic-settings | 环境变量 + .env 加载 |

---

## 📁 项目结构

```
Agent_001/
├── backend/
│   ├── main.py                       # FastAPI 应用入口
│   ├── config.py                     # 全局配置（pydantic-settings）
│   │
│   ├── app/                          # 应用组装层
│   │   ├── container.py              # 系统容器（DI/IoC 核心，243行）
│   │   └── lifecycle.py              # 启动/关闭生命周期
│   │
│   ├── agents/                       # 多智能体系统（核心模块）
│   │   ├── core/                     # 基础设施
│   │   │   ├── event/                #   EventRouter + EventTypes
│   │   │   ├── lifecycle/            #   AgentRegistry（注册/心跳）
│   │   │   ├── messaging/            #   MessageBus + Broker
│   │   │   └── runtime/              #   ResourceManager
│   │   │
│   │   ├── implementations/          # 具体 Agent 实现
│   │   │   ├── base_agent.py         #   BaseAgent 抽象基类
│   │   │   ├── supervisor_agent.py   #   主管 Agent（任务编排）
│   │   │   ├── perception_agent.py   #   感知 Agent（传感器）
│   │   │   ├── navigation_agent.py   #   导航 Agent（路径规划）
│   │   │   ├── execution_agent.py    #   执行 Agent（速度/电源）
│   │   │   ├── world_model_agent.py  #   世界模型 Agent
│   │   │   └── rl_navigation_agent.py#   RL 导航 Agent (pure+hybrid)
│   │   │
│   │   ├── decision/                 # 决策层
│   │   │   ├── navigation/           #   全局规划 + Pure Pursuit
│   │   │   ├── planner/              #   规划器（LLM/Rule/Graph）
│   │   │   └── runtime/              #   任务图执行引擎
│   │   │
│   │   ├── memory/                   # 记忆系统
│   │   │   ├── agent_memory.py       #   统一记忆管理
│   │   │   ├── working_memory.py     #   工作记忆（当前任务）
│   │   │   └── episodic_memory.py    #   情景记忆（历史任务）
│   │   │
│   │   ├── pipeline/                 # 处理管线
│   │   │   ├── pipeline_runner.py    #   管线调度
│   │   │   ├── data_preprocessor.py  #   数据预处理
│   │   │   ├── feature_analyzer.py   #   特征分析
│   │   │   ├── decision_maker.py     #   决策生成
│   │   │   └── command_generator.py  #   命令生成
│   │   │
│   │   ├── runtime/                  # ReAct 运行时
│   │   │   ├── agent_runtime.py      #   Think→Act→Observe→Remember
│   │   │   └── react_prompt.py       #   ReAct 提示词构建
│   │   │
│   │   ├── rl/                       # 强化学习 (RLConfig驱动)
│   │   │   ├── env_wrapper.py        #   RobotGymEnv 365维+6奖励+DR
│   │   │   ├── trainer.py            #   PPO训练 pure+hybrid
│   │   │   └── eval.py               #   多指标评估
│   │   │
│   │   ├── tools/                    # 工具系统（14 个内置工具）
│   │   │   ├── tool_registry.py      #   工具注册表
│   │   │   └── builtin/              #   内置工具集
│   │   │
│   │   ├── schemas/                  # 消息/协议定义
│   │   │   ├── agent_messages.py     #   Agent 消息体
│   │   │   ├── planning_messages.py  #   规划消息体
│   │   │   └── task_messages.py      #   任务消息体
│   │   │
│   │   ├── tests/                    # Agent 测试
│   │   │   ├── unit/                 #   单元测试
│   │   │   ├── integration/          #   集成测试
│   │   │   ├── environment/          #   环境测试
│   │   │   └── ws/                   #   WebSocket 测试
│   │   │
│   │   ├── simulation/               # 仿真环境
│   │   │   ├── environment.py        #   仿真环境
│   │   │   └── scenario_loader.py    #   场景加载器
│   │   │
│   │   └── utils/                    # 工具函数
│   │       ├── coordinate.py         #   坐标系转换
│   │       ├── path_planner.py       #   路径规划辅助
│   │       └── rag_tool.py           #   RAG 工具封装
│   │
│   ├── rag/                          # RAG 系统
│   │   ├── rag_service.py            #   RAG 核心服务
│   │   ├── chat_history.py           #   短期聊天记忆
│   │   ├── long_term_memory.py       #   长期记忆
│   │   ├── chunk_record.py           #   文档分块
│   │   └── vector/                   #   向量存储与检索
│   │       ├── vector_store_new.py   #   ChromaDB 管理
│   │       ├── vector_retriever.py   #   向量检索
│   │       ├── vector_store_retriever.py  # 混合检索
│   │       └── vector_optimization.py     # 向量库优化
│   │
│   ├── llm/                          # LLM 层
│   │   ├── base.py                   #   BaseLLMClient 抽象
│   │   ├── factory.py                #   客户端工厂（多租户）
│   │   ├── openai_client.py          #   OpenAI 兼容客户端
│   │   ├── claude_client.py          #   Anthropic Claude
│   │   ├── gemini_client.py          #   Google Gemini
│   │   ├── adapter_client.py         #   通用适配器
│   │   ├── mock_client.py            #   测试模拟
│   │   └── llm_enums.py              #   枚举定义
│   │
│   ├── models/                       # 领域模型
│   │   ├── db_model/                 #   数据库模型
│   │   ├── cognition/                #   认知模型（世界/房间/覆盖图）
│   │   ├── physics/                  #   物理模型（位姿/动作/环境）
│   │   ├── task/                     #   任务模型（任务/覆盖/使命）
│   │   └── event/                    #   事件模型
│   │
│   ├── services/                     # 服务层
│   │   ├── websocket/                #   WebSocket 连接管理与推送
│   │   ├── state/                    #   状态聚合与前端状态构建
│   │   └── scheduler/                #   定时任务调度
│   │
│   ├── api/                          # API 路由
│   │   ├── db_api/                   #   数据库相关 API
│   │   │   ├── user.py               #   用户 CRUD
│   │   │   ├── chat.py               #   聊天记录
│   │   │   ├── knowledge.py          #   知识库管理
│   │   │   ├── memory.py             #   记忆管理
│   │   │   └── schedule.py           #   定时任务
│   │   └── agent_api/                #   Agent 相关 API
│   │       └── robot.py              #   机器人状态/控制
│   │
│   ├── db/                           # 数据库服务层
│   │   ├── database.py               #   连接池 + 自动建表
│   │   ├── user_service.py           #   用户服务
│   │   ├── chat_service.py           #   聊天服务
│   │   ├── knowledge_service.py      #   知识库服务
│   │   ├── task_service.py           #   任务服务
│   │   └── schedule_service.py       #   调度服务
│   │
│   ├── schemas/                      # Pydantic 数据模型
│   │   ├── user.py                   #   用户
│   │   ├── chat.py                   #   聊天
│   │   ├── knowledge.py              #   知识库
│   │   ├── robot.py                  #   机器人
│   │   └── websocket_protocol.py     #   WebSocket 协议
│   │
│   ├── prompts/                      # 提示词模板（7个场景）
│   │   ├── agent_prompt.txt          #   Agent 通用提示词
│   │   ├── rag_summarize_prompt.txt  #   总结提示词
│   │   ├── rag_repair_prompt.txt     #   维修提示词
│   │   ├── rag_maintain_prompt.txt   #   保养提示词
│   │   ├── rag_guide_prompt.txt      #   选购提示词
│   │   ├── rag_query_routing.txt     #   查询路由提示词
│   │   ├── rag_query_rewriting.txt   #   查询重写提示词
│   │   └── report_prompt.txt         #   报告生成提示词
│   │
│   ├── data/                         # 知识库数据
│   │   ├── 扫地机器人100问.pdf        #   百问百答
│   │   ├── 扫地机器人100问2.txt       #   扩展问答
│   │   ├── 扫拖一体机器人100问.txt    #   扫拖一体
│   │   ├── 故障排除.txt              #   故障排除手册
│   │   ├── 维护保养.txt              #   维护保养手册
│   │   ├── 选购指南.txt              #   选购指南
│   │   └── external/records.csv      #   外部记录
│   │
│   ├── evaluate/                     # 评估模块
│   │   ├── llm_evaluate.py           #   LLM 评估
│   │   ├── ques2query_dataset.json   #   评估数据集
│   │   ├── llamaindex_evaluate.json  #   LlamaIndex 评估
│   │   └── models/                   #   嵌入模型（ONNX）
│   │
│   ├── utils/                        # 工具函数
│   │   ├── file_handler.py           #   文件处理
│   │   ├── data_preparetion.py       #   数据准备
│   │   ├── prompt_loader.py          #   提示词加载
│   │   ├── sse_handler.py            #   SSE 处理
│   │   ├── rag_utils.py              #   RAG 工具
│   │   └── logger_handler.py         #   日志处理
│   │
│   └── logs/                         # 日志文件
│
├── frontend/                         # Vue 3 前端
│   ├── src/
│   │   ├── main.js                   #   应用入口
│   │   ├── App.vue                   #   根组件
│   │   ├── router/index.js           #   路由（7个页面）
│   │   ├── api/                      #   API 封装
│   │   │   ├── index.js              #   Axios 实例
│   │   │   ├── auth.js               #   认证
│   │   │   ├── chat.js               #   聊天
│   │   │   ├── knowledge.js          #   知识库
│   │   │   ├── memory.js             #   记忆
│   │   │   └── robot/                #   机器人 API
│   │   │       ├── robot.js          #   状态/控制
│   │   │       ├── mission.js        #   任务
│   │   │       └── schedule.js       #   定时
│   │   ├── stores/                   #   Pinia 状态
│   │   │   ├── user.js               #   用户状态
│   │   │   ├── chat.js               #   聊天状态
│   │   │   ├── knowledge.js          #   知识库状态
│   │   │   └── robot/                #   机器人状态
│   │   │       ├── robotStore.js     #   实时状态
│   │   │       ├── missionStore.js   #   任务状态
│   │   │       └── eventStore.js     #   事件流
│   │   ├── composables/              #   组合式函数
│   │   │   ├── useAuth.js            #   认证逻辑
│   │   │   ├── useChat.js            #   聊天逻辑
│   │   │   ├── useKnowledge.js       #   知识库逻辑
│   │   │   └── robot/useRobotSSE.js  #   机器人 SSE
│   │   ├── views/                    #   页面
│   │   │   ├── Login.vue             #   登录
│   │   │   ├── Register.vue          #   注册
│   │   │   ├── Chat.vue              #   聊天
│   │   │   ├── KnowledgeBase.vue     #   知识库管理
│   │   │   ├── Memory.vue            #   记忆查看
│   │   │   └── robot/                #   机器人页面
│   │   │       ├── MissionCenter.vue #   任务中心
│   │   │       ├── TaskHistory.vue   #   任务历史
│   │   │       ├── SystemMonitor.vue #   系统监控
│   │   │       └── EventConsole.vue  #   事件控制台
│   │   ├── components/               #   组件
│   │   │   ├── chat/                 #   聊天组件
│   │   │   ├── knowledge/            #   知识库组件
│   │   │   └── robot/                #   机器人组件
│   │   │       ├── dashboard/        #   仪表盘卡片
│   │   │       ├── events/           #   事件组件
│   │   │       ├── mission/          #   任务组件
│   │   │       └── navigation/       #   导航组件（地图/场景）
│   │   ├── layouts/                  #   布局
│   │   │   └── UnifiedLayout.vue     #   统一布局
│   │   └── utils/                    #   工具函数
│   │       ├── request.js            #   HTTP 请求封装
│   │       └── sse.js                #   SSE 客户端
│   ├── index.html
│   ├── vite.config.js
│   ├── package.json
│   └── .env.development
│
├── tests/                            # 顶层测试
│   ├── test_db.py
│   ├── test_rag.py
│   ├── test_memory.py
│   ├── test_vector.py
│   └── test_sse.py
│
└── .env                              # 环境变量
```

---

## 🔄 核心流程

### 用户指令处理流程

```
用户输入指令
      │
      ▼
┌─────────────────┐
│  SupervisorAgent │  接收指令，触发 ReAct 循环
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  AgentRuntime   │  Think → Act → Observe → Remember（最多8步）
│  (ReAct Loop)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      ┌─────────────────┐
│  CallPlanner    │ ──►  │  LLMPlanner +   │  生成任务图
│     Tool        │      │  RulePlanner    │
└────────┬────────┘      └─────────────────┘
         │
         ▼
┌─────────────────┐
│  TaskGraph      │  任务图执行引擎
│  Executor       │  (GraphExecutor / DynamicReplanner)
└────────┬────────┘
         │
    ┌────┴────┬─────────┬──────────┐
    ▼         ▼         ▼          ▼
┌──────┐ ┌──────┐ ┌──────┐ ┌──────────┐
│Percep│ │Navi- │ │Execu │ │WorldModel│
│tion  │ │gation│ │tion  │ │Agent     │
│Agent │ │Agent │ │Agent │ │          │
└──────┘ └──────┘ └──────┘ └──────────┘
    │         │         │          │
    └────┬────┴─────────┴──────────┘
         │
         ▼
┌─────────────────┐
│ RobotState      │  状态聚合 → WebSocket 推前端
│ Aggregator      │
└─────────────────┘
```

### RAG 问答流程

```
用户问题
    │
    ▼
┌──────────────────┐
│ Query Routing    │  LLM 识别问题类型：维修/保养/选购/通用
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Query Rewriting  │  LLM 优化检索查询
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ ChromaDB         │  向量检索（bge-m3 embedding）
│ Vector Retrieval │  Top-K 相关文档片段
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Prompt Template  │  加载对应场景的提示词模板
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ LLM Generation   │  基于检索上下文 + 提示词生成回答
└──────────────────┘
```

---

## ⚡ 快速开始

### 前置条件

- **Python** 3.10+
- **Node.js** 18+
- **MySQL** 5.7+ / 8.0
- **Ollama**（本地 LLM，无需 API Key）或 云端模型 API Key（OpenAI / Claude / Gemini / DeepSeek / GLM / 通义千问 / 豆包 / 文心 / 混元 等 15+ 家）

### 1. 克隆项目

```bash
cd Agent_001
```

### 2. 后端安装

```bash
# 创建虚拟环境
python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate  # Linux/Mac

# 安装 Python 依赖
pip install -r requirements.txt
```

### 3. 配置模型与 API 密钥

点击聊天界面底部模型名称即可打开 **API 密钥管理** 弹窗：
- **选择模型**：在弹窗下拉框中选择本地 Ollama 模型或任意云端模型
- **配置 API Key**：为所选云端模型输入对应提供商的 API 密钥
- **保存即用**：保存后自动切换模型，密钥安全保存在本地服务器

也可以编辑 `.env` 文件配置本地 Ollama 模型：

```env
# MySQL
DB_HOST=localhost
DB_PORT=3306
DB_USER=robotvacuum
DB_PASSWORD=robotvacuum
DB_NAME=robotvacuum

# Ollama
MODEL_NAME=qwen3:8b
BASE_URL=http://localhost:11434
EMBEDDING_NAME=bge-m3
```

### 4. 启动后端

```bash
cd backend
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. 前端安装与启动

```bash
cd frontend
npm install
npm run dev
```

前端运行在 `http://localhost:5173`，自动代理 API 到后端 `http://localhost:8000`。

---

## 📡 API 端点

### REST API（`/api`）

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/user/login` | 用户登录 |
| `POST` | `/api/user/register` | 用户注册 |
| `GET` | `/api/user/info` | 获取用户信息 |
| `POST` | `/api/chat/send` | 发送聊天消息（SSE 流式响应） |
| `GET` | `/api/chat/history` | 获取聊天历史 |
| `POST` | `/api/knowledge/upload` | 上传知识库文档 |
| `GET` | `/api/knowledge/list` | 获取知识库列表 |
| `DELETE` | `/api/knowledge/{id}` | 删除知识库文档 |
| `GET` | `/api/memory/query` | 查询长期记忆 |
| `POST` | `/api/memory/save` | 保存长期记忆 |
| `GET` | `/api/robot/state` | 获取机器人实时状态 |
| `GET` | `/api/robot/world` | 获取世界模型 |
| `POST` | `/api/robot/task` | 提交任务指令 |
| `POST` | `/api/robot/control` | 发送控制指令 |
| `GET` | `/api/robot/missions` | 获取任务列表 |
| `GET` | `/api/robot/missions/{id}` | 获取任务详情 |
| `GET` | `/api/robot/missions/{id}/replay` | 获取任务回放数据 |
| `GET` | `/api/schedules` | 获取定时任务列表 |
| `POST` | `/api/schedules` | 创建定时任务 |
| `PUT` | `/api/schedules/{id}` | 更新定时任务 |
| `DELETE` | `/api/schedules/{id}` | 删除定时任务 |

### WebSocket

| 端点 | 说明 |
|------|------|
| `/ws/robot` | 机器人实时状态推送（位姿、电池、进度、事件） |

### 基础端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/` | 系统状态 |
| `GET` | `/health` | 健康检查 |

---

## 🧠 核心模块详解

### Multi-Agent 系统

| Agent | 职责 | 关键特性 |
|-------|------|----------|
| **SupervisorAgent** | 任务编排、用户交互、ReAct 调用 | 任务图下发、失败处理、历史记录 |
| **PerceptionAgent** | 传感器数据处理 | 障碍物检测、环境感知 |
| **NavigationAgent** | 路径规划与路径跟踪 | 全局规划（A\*） + Pure Pursuit 局部跟踪 |
| **ExecutionAgent** | 速度指令执行、电源管理 | 电源状态机（7状态）、碰撞检测 |
| **WorldModelAgent** | 世界模型维护 | 房间地图、覆盖图、物体追踪 |
| **RLNavigationAgent** | 强化学习导航 | 365维观测、6项奖励、域随机化环境、pure+hybrid双模式 |

### Agent 间通信

所有 Agent 通过 **MessageBus**（发布-订阅）和 **EventRouter**（事件广播）通信：

```
Agent A ──publish──► MessageBus ──dispatch──► Agent B (订阅者)
Agent A ──emit─────► EventRouter ─broadcast──► 前端 (SSE/WS)
```

消息类型：`COMMAND` / `ROBOT_STATE` / `SIMULATION_STATE` / `NAVIGATION_REQUEST` / `EXECUTION` / `HEARTBEAT` / `TASK_CONTROL`

### ReAct 运行时

```
┌─────────────────────────────────────────┐
│              ReAct Loop                  │
│                                          │
│  ┌──────────┐   ┌──────────┐            │
│  │  THINK   │──►│   ACT    │            │
│  │ (LLM)    │   │ (Tools)  │            │
│  └──────────┘   └────┬─────┘            │
│        ▲              │                  │
│        │         ┌────▼─────┐            │
│        │         │ OBSERVE  │            │
│        │         │ (结果)    │            │
│        │         └────┬─────┘            │
│        │              │                  │
│        │         ┌────▼─────┐            │
│        └─────────│ REMEMBER │            │
│                  │ (记忆存储)│            │
│                  └──────────┘            │
│                                          │
│  参数: MAX_STEPS=8, LLM_RETRIES=2        │
│  LLM: qwen3:8b (via Ollama)             │
└─────────────────────────────────────────┘
```

### RAG 系统

- **查询路由**：LLM 自动识别问题类型 → 路由到对应知识库
  - `general` → 通用知识库
  - `repair` → 维修知识库
  - `maintain` → 保养知识库
  - `guide` → 选购指南知识库
- **向量检索**：bge-m3 embedding + ChromaDB，Top-K=3 检索
- **长期记忆**：自动存储和检索用户偏好与历史交互
- **文档分块**：chunk_size=600, chunk_overlap=100

### 任务规划系统

- **LLMPlanner**：利用 LLM 理解自然语言指令，生成结构化任务图
- **RulePlanner**：基于预定义规则快速响应简单指令
- **PlanningPostProcessor**：后处理（电池阈值检查、任务可行性验证）
- **GraphExecutor**：执行任务图，支持并行/串行节点
- **DynamicReplanner**：执行过程中动态重规划

---

## 🏭 数据库

MySQL 自动建表，包含以下表：

| 表名 | 说明 |
|------|------|
| `users` | 用户表 |
| `chat_history` | 聊天记录 |
| `knowledge_base` | 知识库（支持公共/私有） |
| `knowledge_doc` | 知识文档 |
| `document_chunks` | 文档切片（RAG 检索用） |
| `task_history` | 任务历史 |
| `mission_history` | 任务执行记录 |
| `mission_task_nodes` | 任务节点详情 |
| `mission_replay` | 任务回放数据（轨迹+覆盖度） |
| `schedules` | 定时任务 |

---

## 🧪 测试

# 运行所有测试
pytest tests/

# Agent 单元测试
python -m backend.agents.tests.unit.run_tools
python -m backend.agents.tests.unit.run_react
python -m backend.agents.tests.unit.run_memory

# Agent 集成测试
python -m backend.agents.tests.integration.run_agents_integration
python -m backend.agents.tests.integration.run_supervisor_integration

# WebSocket 测试
python -m backend.agents.tests.ws.robot_test_websocket
### 强化学习训练

# 训练 Pure 模型（365维观测，纯反应式）
python -m backend.agents.scripts.train_rl pure

# 训练 Hybrid 模型（367维观测，目标导向）
python -m backend.agents.scripts.train_rl hybrid

# 同时训练两个模型
python -m backend.agents.scripts.train_rl both

# 评估训练好的模型
python -m backend.agents.scripts.evaluate_rl ./rl_models/pure/final_robot_policy.zip
python -m backend.agents.scripts.evaluate_rl ./rl_models/hybrid/final_robot_policy.zip
`

```

---

## 📝 开发指南

### 添加新的 Agent

1. 继承 `BaseAgent`（`backend/agents/implementations/base_agent.py`）
2. 实现 `on_start()` / `on_stop()` / `_subscribe_messages()`
3. 在 `SystemContainer.__init__()` 中注册
4. 添加到 `self._components` 列表

### 添加新的 ReAct 工具

1. 创建工具类，实现 `name`、`description`、`async execute(args)` 
2. 在 `SystemContainer` 中 `tool_registry.register_many()` 注册

### 添加新的提示词模板

1. 在 `backend/prompts/` 添加 `.txt` 文件
2. 在 `backend/config.py` 的 `Settings` 中添加路径
3. 在 `backend/utils/prompt_loader.py` 中加载

---

## 🔧 配置说明

详见 `backend/config.py` 的 `Settings` 类：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `model_name` | `qwen3:8b` | 主 LLM 模型 |
| `model_name2` | `glm4:9b` | 备用 LLM 模型 |
| `base_url` | `http://localhost:11434` | Ollama 服务地址 |
| `embedding_name` | `bge-m3` | 嵌入模型 |
| `temperature` | `0.2` | LLM 温度 |
| `chunk_size` | `600` | 文档分块大小 |
| `chunk_overlap` | `100` | 分块重叠 |
| `k` | `3` | 向量检索 Top-K |
| `db_host` | `localhost` | MySQL 地址 |
| `long_term_max_memories` | `200` | 长期记忆上限 |

---

## 📄 License

Internal Project