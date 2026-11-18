# KnowFlow / 智识库

自动生长式个人知识体系工具。当前实现覆盖架构文档的 MVP、一期扩展、知识树、RAG 问答、LLM Wiki，以及可观察、可停止的 AI 内容整理流程。

## 项目结构

```text
backend/
├── app/
│   ├── api/v1/              # 认证、知识库、内容、模板、检索、合并、知识点、LLM
│   ├── core/                # 配置、数据库、认证、缓存、异常
│   ├── models/              # SQLAlchemy 领域模型
│   ├── schemas/             # Pydantic 请求与响应结构
│   ├── services/            # 应用服务和领域流程
│   ├── infrastructure/      # LLM、解析器、向量库、仓储
│   └── workers/             # FastAPI BackgroundTasks 与 Celery 任务
├── alembic/                 # SQLite / PostgreSQL 迁移
├── tests/                   # API 集成测试
├── requirements.txt
└── Dockerfile

frontend/
├── src/
│   ├── app/                 # Next.js App Router、主题和登录页
│   ├── components/          # 工作台、知识树、问答、模板、合并、设置
│   ├── services/            # FastAPI 接口客户端
│   ├── stores/              # Zustand 状态
│   ├── types/
│   └── utils/
├── package.json
└── Dockerfile

docker-compose.yml           # 完整生产编排
nginx.conf                   # 反向代理与 API 限流
prometheus.yml               # 后端指标采集
```

## 启动方式

项目支持两种启动方式。日常联调推荐使用 Docker Compose；只修改后端或前端代码时，也可以分别启动本地服务。

### 方式一：Docker Compose（推荐）

确保 Docker Desktop 已启动，然后在项目根目录执行：

```powershell
cd D:\LIN_NOTE
docker desktop status
Copy-Item backend\.env.example backend\.env -ErrorAction SilentlyContinue
docker compose up -d --build
```

首次启动会构建前后端镜像，并启动 PostgreSQL、Redis、ChromaDB、MinIO、Celery、Prometheus、Nginx 和应用服务。之后只修改代码时可直接执行：

```powershell
docker compose up -d
```

查看服务状态和日志：

```powershell
docker compose ps
docker compose logs -f backend
```

启动后可访问：

- 应用入口：http://localhost
- 后端 API：http://localhost:8000
- API 文档：http://localhost:8000/docs
- 后端健康检查：http://localhost:8000/health
- Prometheus 指标：http://localhost:8000/metrics
- 前端直连：http://localhost:3000
- MinIO 控制台：http://localhost:9001

Windows 下可用以下命令快速验证健康状态：

```powershell
Invoke-WebRequest -UseBasicParsing http://localhost/health
Invoke-WebRequest -UseBasicParsing http://localhost:8000/health
Invoke-WebRequest -UseBasicParsing http://localhost:3000
```

停止服务（保留数据库和其他数据卷）：

```powershell
docker compose down
```

### 方式二：本地开发启动

#### 1. 后端

Windows 可直接运行：

```powershell
cd backend
.\start.ps1
```

脚本会检查并重建失效的虚拟环境、安装依赖、生成 `.env`、执行迁移并启动 API。

手动启动：

```powershell
cd backend
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic -c alembic.ini upgrade head
uvicorn app.main:app --reload
```

- API：http://localhost:8000
- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health
- Prometheus 指标：http://localhost:8000/metrics

未配置 LLM 或 ChromaDB 时，内容提纯、摘要、知识点、合并和语义搜索会使用本地降级逻辑，基础流程仍可运行。LLM 提纯的语义筛选能力强于本地规则，正式使用时建议配置可用模型。

图片 OCR 需要系统安装 Tesseract；Docker 镜像已包含英文和简体中文语言包。

#### 2. 前端

```powershell
cd frontend
Copy-Item .env.example .env.local
npm install
npm run dev
```

访问：http://localhost:3000

`NEXT_PUBLIC_API_URL` 默认是 `http://localhost:8000/api/v1`。

## 浏览器辅助导入

小红书等平台会对服务端匿名读取施加登录、动态签名和风控限制。KnowFlow 提供一个不上传登录 Cookie 的浏览器采集助手：

1. 登录 KnowFlow，点击“收进一条新内容”；
2. 选择“浏览器采集”；
3. 将“保存到 KnowFlow”按钮拖到浏览器书签栏；
4. 在已经登录且内容加载完成的网页中点击该书签；
5. 在新打开的采集页检查正文、图片数量和字幕状态，选择知识库后确认导入。

采集数据通过 URL `#fragment` 带回 KnowFlow，片段不会发送到网页服务器或写入访问日志；保存接口仍要求有效的 KnowFlow 登录令牌。

- 普通文章：采集标题、描述、结构化正文和当前选中文本；
- 多图笔记：优先读取页面内嵌的完整图片列表，最多对 10 张图片执行 OCR，并合并为一条内容；
- 视频笔记：采集标题、发布文案、封面和网页已经提供的字幕轨；
- 视频页面没有字幕时，不会把音轨误标为已转写。当前版本暂不包含视频语音识别，导入前会明确提示。

书签脚本只在用户主动点击时运行，不读取或上传平台 Cookie。若图片 CDN 地址过期或限制服务器下载，网页正文仍可导入，相应图片会记录为 OCR 失败。

本地启动后端时，`backend\.venv` 如果来自其他 Python 安装位置，建议删除后重新执行 `.\start.ps1`，脚本会自动重建虚拟环境并安装依赖。

## 校验

后端：

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall -q app
```

前端：

```powershell
cd frontend
npm run lint
npm run typecheck
npm run build
```

当前基线（2026-10-09）：后端 `20 passed`；前端 lint、类型检查和生产构建均通过。测试数量会随功能增长，以本地实际输出为准。

## AI 整理流程

文本、链接/视频页面和图片 OCR 内容都会先经过统一的语义提纯，再生成摘要、知识点和检索索引：

```text
原始材料（永久保留，用于溯源）
  → 语义提纯（只保留与主题有关、可独立理解、可复用的知识）
  → 摘要与知识点切片
  → 关键词/向量检索索引
```

提纯不仅过滤广告，还会排除与主体知识无关的导航、按钮、评论互动、联系方式、版权模板、重复内容、OCR 乱码及其他页面噪声。LLM 不可用时会使用本地规则降级，但语义判断能力弱于可用模型。

内容处理状态如下：

| 状态 | 含义 | 前端表现 |
| --- | --- | --- |
| `pending` | 后台正在提纯、摘要或切片 | 显示整理进度，并允许停止 |
| `finalizing` | 新结果正在进行原子写入 | 显示“正在写入”，此时不再允许停止 |
| `processed` | 整理和结构化写入完成 | 刷新提纯正文、摘要与知识点 |
| `failed` | 任务失败，后端保留内部错误信息 | 显示失败和重试入口 |
| `cancelled` | 用户主动停止 | 保留原有结果，可重新整理 |

在内容详情点击“重新整理”前，界面会说明现有 AI 摘要和自动生成知识点将被替换，原始内容不变。整理中可以点击“停止整理”：同一后端进程会尝试立即取消正在等待的模型协程；跨进程或模型供应商暂不支持立即断开时，任务会在下一个检查点停止。无论哪种情况，已取消任务的未完成结果都不会写入，也不能覆盖之后启动的新任务。

相关接口：

- `POST /api/v1/contents/{content_id}/process`：启动重新整理；
- `POST /api/v1/contents/{content_id}/process/cancel`：停止当前整理；
- `GET /api/v1/contents/{content_id}`：读取状态，前端整理期间每 1.5 秒轮询。

内容导入和页面内重新整理当前由 FastAPI `BackgroundTasks` 执行；仓库同时保留 Celery 任务实现，供独立工作进程和后续队列化演进使用。

## LLM Wiki 问答流程

```text
用户提问
  → 按用户与知识库范围查找已发布 Wiki 条目
  → 未命中时对提纯后的知识切片执行混合 RAG 检索
  → LLM 根据检索上下文回答并返回引用
  → 同一规范化问题达到阈值后自动发布到 Wiki
  → 后续同问题直接返回 Wiki 答案
```

默认发布阈值为第 5 次提问，可通过 `LLM_WIKI_PUBLISH_THRESHOLD` 调整；可通过 `LLM_WIKI_ENABLED` 总体启停。匹配采用规范化后的精确问题哈希，不会把语义不同的问题错误合并。Wiki 条目保留答案、引用来源、提问次数和发布时间，并支持列表、编辑、发布状态调整与删除。

## 主要功能

- 知识库 CRUD、统计、Markdown / JSON 导出
- 文本、链接/视频页面、图片 OCR、已登录浏览器辅助导入
- 全来源 AI 提纯：按主体知识相关性过滤推广、页面组件、互动引导、OCR 乱码等非知识噪声
- 基于提纯正文的 AI 摘要、知识切片、详略风格和自定义字段模板
- 重新整理确认、实时轮询、成功/失败反馈、主动停止和安全重试
- 内容与知识点编辑
- 关键词、向量和混合检索
- 相似检测、合并预览、合并历史
- 知识树与知识问答
- LLM Wiki 优先命中、RAG 回退和高频问题自动沉淀
- 用户资料和模型连接状态
- 本地降级、后台任务、监控和完整容器编排

详细完成状态见 [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)。

> 从旧版本升级后，历史内容不会再以未经提纯的原文参与检索。请在内容详情中点击“重新整理”，生成提纯正文和新的知识切片；新导入内容会自动执行该流程。
