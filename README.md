# NewsFlow

NewsFlow 是一个轻量级新闻数据采集与推送服务框架，基于微服务架构设计，支持从多个主流新闻源采集数据并推送至多种目标平台。

## 架构概览

NewsFlow 采用分层架构设计，整体分为四个层次：

### 接入层

FastAPI 应用入口 (`main.py`)，负责路由注册和服务启动。

### 服务层

- **采集服务** (`/collect/*`)：提供新闻数据采集能力
- **数据处理服务** (`/processor/*`)：提供数据格式化能力
- **推送服务** (`/push/*`)：提供消息推送能力

### 核心组件层

| 组件            | 职责                                                 |
| --------------- | ---------------------------------------------------- |
| `BrowserClient` | 基于 Playwright 的无头浏览器，渲染动态网页内容       |
| `Parser`        | 策略模式实现的网页解析器，提取结构化数据             |
| `BaseFormatter` | 策略模式实现的格式化器，将数据转换为 Markdown 字符串 |
| `BaseSender`    | 策略模式实现的推送器，对接各平台 Webhook             |

### 数据源与推送目标

- 数据源：Sina、163、Tencent
- 推送目标：企业微信

```
main.py
├── collector/
│   ├── services.py      (REST API: /collect)
│   ├── browser_client.py (Playwright 浏览器客户端)
│   └── parser.py        (网页解析器: Sina/163/Tencent)
├── processor/
│   ├── services.py      (REST API: /processor)
│   └── formatter.py     (格式化器: CollectFormatter)
└── pusher/
    ├── services.py      (REST API: /push)
    └── senders.py        (推送器: WeChat)
```

## 核心模块

### 1. 入口模块 (`main.py`)

FastAPI 应用入口，注册采集和推送服务路由，提供开发模式和命令行两种启动方式。

### 2. 配置模块 (`config.py`)

集中管理项目配置，包括：

- 服务端口配置
- 浏览器无头模式、超时、等待策略
- 并发数控制

### 3. 数据模型 (`schemas.py`)

定义核心数据结构：

- `ParsedItem`: 新闻条目（标题、URL、来源）
- `CollectRequest/CollectResponse`: 采集请求/响应
- `FormatRequest/FormatResponse`: 格式化请求/响应
- `PushRequest/PushResponse`: 推送请求/响应

### 4. 采集服务层 (`collector/`)

| 模块                | 功能                                                           |
| ------------------- | -------------------------------------------------------------- |
| `services.py`       | 采集路由定义，处理串行/并行采集策略                            |
| `browser_client.py` | 基于 Playwright 的异步浏览器客户端，支持页面渲染和批量并发获取 |
| `parser.py`         | 策略模式实现的解析器，支持 Sina、163、Tencent 三个新闻源       |

**采集接口：**

- `GET /collect/sources` - 获取可用数据源列表
- `GET /collect/health` - 健康检查
- `POST /collect` - 执行数据采集

### 5. 处理器服务层 (`processor/`)

| 模块           | 功能                                           |
| -------------- | ---------------------------------------------- |
| `services.py`  | 格式化路由定义，支持单个/批量格式化请求        |
| `formatter.py` | 策略模式实现的格式化器，支持 Markdown 格式转换 |

**格式化接口：**

- `GET /processor/health` - 健康检查
- `POST /processor/format` - 格式化数据为 Markdown 字符串

### 6. 推送服务层 (`pusher/`)

| 模块          | 功能                                       |
| ------------- | ------------------------------------------ |
| `services.py` | 推送路由定义，接收格式化后的字符串列表     |
| `senders.py`  | 策略模式实现的推送器，支持企业微信 Webhook |

**推送接口：**

- `GET /push/targets` - 获取可用推送目标列表
- `GET /push/health` - 健康检查
- `POST /push` - 执行消息推送

## 支持的数据源

| 源标识    | 网站     |
| --------- | -------- |
| `sina`    | 新浪新闻 |
| `163`     | 网易新闻 |
| `tencent` | 腾讯新闻 |

## 支持的推送方

| 推送标识 | 平台     | 配置项               |
| -------- | -------- | -------------------- |
| `wechat` | 企业微信 | `WECHAT_WEBHOOK_URL` |

## 使用方式

### 1. 安装依赖

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. 配置环境变量

在 `.env` 文件中配置：

```env
WECHAT_WEBHOOK_URL=your_wechat_webhook_url
```

### 3. 启动服务

**开发模式：**

```bash
python main.py
```

**命令行模式：**

```bash
uvicorn main:app --host 0.0.0.0 --port 23119 --reload
```

## API 使用示例

### 1. 采集新闻

```bash
curl -X POST http://localhost:23119/collect \
  -H "Content-Type: application/json" \
  -d '{"sources": ["sina", "163"]}'
```

### 2. 格式化数据

```bash
curl -X POST http://localhost:23119/processor/format \
  -H "Content-Type: application/json" \
  -d '{"data": [{"collect": {"sina": [{"title": "新闻标题", "url": "https://..."}]}}]}'
```

### 3. 推送新闻

```bash
curl -X POST http://localhost:23119/push \
  -H "Content-Type: application/json" \
  -d '{"items": ["# sina 资讯\n- [新闻标题](https://...)"], "targets": ["wechat"]}'
```

## 技术栈

- **Web 框架**: FastAPI + Uvicorn
- **浏览器自动化**: Playwright
- **HTML 解析**: parsel
- **数据验证**: Pydantic
- **HTTP 客户端**: httpx
- **配置管理**: python-dotenv
