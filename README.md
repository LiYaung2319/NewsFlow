# NewsFlow

NewsFlow 是一个轻量级的数据采集与推送服务框架，支持从多种新闻源采集数据，并将数据推送到多个目标平台。项目采用微服务架构设计，采集与推送功能分离，可独立部署和扩展。

## 目录

- [项目定位](#项目定位)
- [项目架构](#项目架构)
- [快速开始](#快速开始)
- [项目结构](#项目结构)
- [配置文件](#配置文件)
- [API 文档](#api-文档)
- [测试指南](#测试指南)
- [未来规划](#未来规划)

## 项目定位

### 当前功能

NewsFlow 目前提供以下核心能力：

- **多源采集**：支持从新浪、网易、腾讯等新闻网站采集数据
- **多目标推送**：支持企业微信、钉钉、邮件等多种推送渠道
- **灵活配置**：通过配置文件管理数据源和推送目标
- **统一接口**：RESTful API 设计，便于与其他系统集成

### 适用场景

NewsFlow 特别适合以下使用场景：

1. **定时新闻推送**：定时采集新闻并推送到团队群聊
2. **数据管道**：作为数据流转的中间层，连接数据源与目标平台
3. **自动化工作流**：与 n8n、Make 等工作流工具配合使用

### 建议的集成方式

NewsFlow 建议与以下工作流工具配合使用：

- **n8n**：可通过 HTTP Request 节点调用 NewsFlow API
- **Make（原 Integromat）**：可通过 HTTP 模块调用 NewsFlow
- **Node-RED**：可通过 http request 节点调用 NewsFlow

这种集成方式让 NewsFlow 专注于数据采集与推送的核心逻辑，而工作流工具负责调度和编排。

## 项目架构

### 整体架构

NewsFlow 采用三层微服务架构设计：

```
+------------------+     +------------------+
|   采集服务        |     |   推送服务        |
|  (Collector)     |     |   (Pusher)        |
|  端口: 23119     |     |  端口: 23120      |
+--------+---------+     +--------+---------+
         |                        |
         |    数据流转             |
         +----------------------->+
                  |
                  v
         +------------------+
         |   外部系统       |
         | (n8n/工作流)    |
         +------------------+
```

### 服务层说明

#### 采集服务（Collector Service）

采集服务负责从配置的各个新闻源获取数据。该服务包含以下功能模块：

- **HTTP 客户端**：使用 httpx 异步库进行网络请求
- **解析器**：针对不同网站结构实现专用解析逻辑
- **路由层**：提供 RESTful API 接口

采集服务支持并发采集多个数据源，可配置并发数以控制请求频率。

#### 推送服务（Pusher Service）

推送服务负责将数据推送到各个目标平台。该服务采用策略模式设计：

- **发送器**：针对不同平台实现消息发送逻辑
- **路由层**：统一处理推送请求
- **批处理**：支持一次推送多个目标

### 数据流

NewsFlow 的典型数据流如下：

1. 外部系统或调度器触发采集请求
2. 采集服务从配置的新闻源获取 HTML 内容
3. 解析器将 HTML 解析为结构化数据
4. 外部系统获取采集结果
5. 外部系统调用推送接口将数据发送到目标平台

## 快速开始

### 环境要求

- Python 3.8+
- uv 或 pip 包管理器

### 安装依赖

```bash
# 使用 uv（推荐）
uv pip install -e .

# 或使用 pip
pip install -e .
```

### 安装测试依赖

```bash
pip install aiohttp
```

### 启动服务

NewsFlow 支持两种服务角色，可以独立运行：

```bash
# 启动采集服务（端口 23119）
python main.py --role collector

# 启动推送服务（端口 23120）
python main.py --role pusher

# 不指定角色时，使用配置默认值
python main.py
```

### 运行测试

```bash
# 运行全部接口测试
python test.py
```

测试脚本会自动：

1. 检测并释放被占用的端口
2. 启动采集服务和推送服务
3. 执行全部测试用例
4. 停止测试服务

## 项目结构

```
NewsFlow/
├── main.py                    # 程序入口，负责服务启动
├── config.py                  # 全局配置文件
├── test.py                    # 接口测试脚本
├── collector/                 # 采集核心模块
│   ├── client.py              # HTTP 客户端实现
│   ├── parser.py              # 数据解析器
│   └── protocol.py            # 数据结构定义
├── processor/                 # 数据处理模块
│   ├── __init__.py            # 模块导出
│   ├── base.py                # 处理器抽象基类
│   ├── formatter.py           # 数据格式化实现
│   ├── processor.py           # 处理链主类
│   └── registry.py            # 处理器注册表
├── services/                  # 服务层
│   ├── collector/             # 采集服务
│   │   ├── router.py          # API 路由
│   │   ├── schemas.py         # 请求/响应模型
│   │   └── deps.py            # 依赖注入
│   └── pusher/                # 推送服务
│       ├── router.py          # API 路由
│       ├── schemas.py         # 请求/响应模型
│       └── senders.py         # 消息发送器
└── services/__init__.py       # 服务模块导出
```

### 核心模块说明

#### main.py

项目入口文件，负责解析命令行参数并启动对应服务。

**主要功能：**

- 解析 `--role` 参数决定启动哪个服务
- 从 `config.py` 读取服务配置
- 使用 uvicorn 启动 FastAPI 应用

#### config.py

全局配置类，定义了所有可配置的参数。

**配置项：**

- 服务端口配置
- HTTP 请求超时和并发控制
- 推送目标配置

详细说明见[配置文件](#配置文件)章节。

#### collector/client.py

HTTP 异步客户端，负责发起网络请求。

**主要类：**

- `CollectorClient`：异步 HTTP 客户端，支持 GET/POST 请求

**功能特性：**

- 异步并发请求控制
- 自动处理重定向
- 默认请求头配置

#### collector/parser.py

数据解析器模块，包含各数据源的解析逻辑。

**主要类：**

- `BaseParser`：解析器抽象基类
- `SinaParser`：新浪新闻解析器
- `NeteaseParser`：网易新闻解析器
- `TencentParser`：腾讯新闻解析器
- `ArticleParser`：通用文章解析器

**注册表：**

- `SOURCES`：数据源配置字典
- `SOURCES_KEYS`：可用数据源列表

#### collector/protocol.py

数据结构定义模块。

**主要类：**

- `ParsedItem`：解析结果数据结构

#### services/collector/

采集服务的 API 层实现。

**文件说明：**

- `router.py`：API 路由定义
- `schemas.py`：请求/响应数据模型
- `deps.py`：FastAPI 依赖注入

#### services/pusher/

推送服务的 API 层和发送器实现。

**文件说明：**

- `router.py`：API 路由定义
- `schemas.py`：请求/响应数据模型
- `senders.py`：各平台消息发送器实现

#### processor/

数据处理模块，提供数据格式化、清洗、转换等处理能力。

**设计理念：**

采用插件式处理器架构，支持处理器按需组合，形成处理管道：

```
原始数据 → [处理器1] → [处理器2] → ... → [格式化] → 输出
```

**文件说明：**

- `base.py`：处理器抽象基类 `BaseProcessor`
- `formatter.py`：数据格式化实现，支持多种输出格式
- `processor.py`：`DataProcessor` 处理链主类
- `registry.py`：处理器注册表，支持动态注册和加载

**当前已实现功能：**

- **格式化**：`format_item()`、`format_batch()` 支持 markdown、text、plain 三种格式

**规划中功能：**

- 去重处理器
- 筛选处理器
- 关键词处理器
- 相似度对比
- 推荐排序

#### processor/formatter.py

数据格式化模块，负责将结构化数据转换为指定格式的字符串。

**支持格式：**

| 格式类型 | 说明 | 输出示例 |
| -------- | ---- | -------- |
| `markdown` | Markdown 格式，适合企业微信等平台 | `# 标题\n> 来源：xxx\n---\n[查看详情](url)` |
| `text` | 纯文本格式，适合简单展示 | `标题 (来源)\nurl` |
| `plain` | 极简格式，无额外装饰 | `标题\n来源\nurl` |

**核心函数：**

```python
from processor import format_item, format_batch

# 单条格式化
result = format_item({"title": "新闻标题", "url": "https://...", "source": "sina"}, "markdown")

# 批量格式化
results = format_batch(items, format_type="markdown")
```

#### processor/processor.py

数据处理链主类，协调多个处理器按顺序处理数据。

**主要类：**

- `DataProcessor`：处理链主类

**使用示例：**

```python
from processor import DataProcessor

processor = DataProcessor()
processor.add_processor(DedupProcessor())  # 添加去重处理器
processor.add_processor(FilterProcessor(keywords=["AI"]))  # 添加筛选处理器
processor.set_format("markdown")

result = await processor.run(items)  # 返回格式化后的字符串列表
```

## 配置文件

### 配置结构

`config.py` 文件包含项目的全部可配置参数。

#### 服务配置

```python
class Settings:
    # 采集服务配置
    collector_host: str = "0.0.0.0"  # 监听地址
    collector_port: int = 23119       # 监听端口

    # 推送服务配置
    pusher_host: str = "0.0.0.0"     # 监听地址
    pusher_port: int = 23120          # 监听端口
```

| 参数             | 默认值      | 说明                                         |
| ---------------- | ----------- | -------------------------------------------- |
| `collector_host` | `"0.0.0.0"` | 采集服务监听地址，`0.0.0.0` 表示监听所有网卡 |
| `collector_port` | `23119`     | 采集服务端口号                               |
| `pusher_host`    | `"0.0.0.0"` | 推送服务监听地址                             |
| `pusher_port`    | `23120`     | 推送服务端口号                               |

#### HTTP 请求配置

```python
    timeout: float = 30.0       # 请求超时时间（秒）
    max_concurrency: int = 10  # 最大并发数
```

| 参数              | 默认值 | 说明                         |
| ----------------- | ------ | ---------------------------- |
| `timeout`         | `30.0` | 单次 HTTP 请求的最大等待时间 |
| `max_concurrency` | `10`   | 并发采集时的最大并行请求数   |

#### 启动配置

```python
    service_token: str = ""            # 服务间认证 Token
    default_role: str = "pusher"       # 默认启动角色
```

| 参数            | 默认值     | 说明                                 |
| --------------- | ---------- | ------------------------------------ |
| `service_token` | `""`       | 预留字段，用于服务间通信认证         |
| `default_role`  | `"pusher"` | 未指定 `--role` 参数时的默认启动角色 |

#### 推送目标配置

```python
    push_targets: dict = {
        "wechat_main": {
            "type": "wechat",
            "webhook_url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=...",
        }
    }
```

| 参数           | 说明                                   |
| -------------- | -------------------------------------- |
| `push_targets` | 推送目标配置字典，键为目标标识符       |
| `type`         | 目标类型，对应 `senders.py` 中的发送器 |
| `webhook_url`  | 目标平台的 Webhook 地址                |

##### 配置示例

**添加新的企业微信目标：**

```python
push_targets: dict = {
    "wechat_main": {
        "type": "wechat",
        "webhook_url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=主群KEY",
    },
    "wechat_alert": {
        "type": "wechat",
        "webhook_url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=告警群KEY",
    },
}
```

**禁用某个目标：**

将 `webhook_url` 设置为空字符串即可禁用：

```python
push_targets: dict = {
    "wechat_test": {
        "type": "wechat",
        "webhook_url": "",  # 空字符串表示禁用
    },
}
```

## API 文档

### 采集服务 API

采集服务运行在端口 23119。

#### 健康检查

检查采集服务是否正常运行。

**请求：**

```bash
# Windows
curl http://localhost:23119/collect/health

# macOS / Linux
curl http://localhost:23119/collect/health
```

**响应：**

```json
{
  "status": "healthy"
}
```

#### 获取可用源列表

查询当前配置的所有可用数据源。

**请求：**

```bash
# Windows
curl http://localhost:23119/collect/sources

# macOS / Linux
curl http://localhost:23119/collect/sources
```

**响应：**

```json
{
  "sources": ["sina", "163", "tencent"]
}
```

#### 采集数据

从指定数据源采集新闻数据。

**请求：**

| 参数          | 类型      | 必填 | 说明                |
| ------------- | --------- | ---- | ------------------- |
| `sources`     | List[str] | 是   | 要采集的数据源列表  |
| `concurrency` | int       | 否   | 并发请求数，默认 10 |

**使用示例：**

```bash
# Windows - 采集全部数据源
curl -X POST http://localhost:23119/collect ^
  -H "Content-Type: application/json" ^
  -d "{\"sources\":[\"all\"]}"

# Windows - 采集指定数据源
curl -X POST http://localhost:23119/collect ^
  -H "Content-Type: application/json" ^
  -d "{\"sources\":[\"sina\"]}"

# Windows - 空数组表示全部
curl -X POST http://localhost:23119/collect ^
  -H "Content-Type: application/json" ^
  -d "{\"sources\":[]}"

# macOS / Linux - 采集全部数据源
curl -X POST http://localhost:23119/collect \
  -H "Content-Type: application/json" \
  -d '{"sources":["all"]}'

# macOS / Linux - 采集指定数据源
curl -X POST http://localhost:23119/collect \
  -H "Content-Type: application/json" \
  -d '{"sources":["sina"]}'
```

**响应：**

```json
{
    "status": "success",
    "total_sources": 2,
    "items_by_source": {
        "sina": [
            {
                "title": "新闻标题",
                "url": "https://news.sina.com.cn/...",
                "source": "sina"
            }
        ],
        "163": [...]
    },
    "total_items": 15,
    "errors": null
}
```

---

### 推送服务 API

推送服务运行在端口 23120。

#### 健康检查

检查推送服务是否正常运行。

**请求：**

```bash
# Windows
curl http://localhost:23120/push/health

# macOS / Linux
curl http://localhost:23120/push/health
```

**响应：**

```json
{
  "status": "healthy"
}
```

#### 获取可用目标列表

查询当前配置的所有可用推送目标。

**请求：**

```bash
# Windows
curl http://localhost:23120/push/targets

# macOS / Linux
curl http://localhost:23120/push/targets
```

**响应：**

```json
{
  "targets": [
    {
      "name": "wechat_main",
      "type": "wechat",
      "enabled": true
    }
  ]
}
```

#### 推送数据

将数据推送到指定目标平台。

**请求：**

| 参数      | 类型       | 必填 | 说明                                        |
| --------- | ---------- | ---- | ------------------------------------------- |
| `items`   | List[Dict] | 是   | 要推送的数据列表                            |
| `targets` | List[str]  | 是   | 目标列表，传递 `["all"]` 或空数组推送到全部 |

**数据项字段：**

| 字段     | 类型 | 说明     |
| -------- | ---- | -------- |
| `title`  | str  | 消息标题 |
| `url`    | str  | 原文链接 |
| `source` | str  | 来源标识 |

**使用示例：**

```bash
# Windows - 推送到全部目标
curl -X POST http://localhost:23120/push ^
  -H "Content-Type: application/json" ^
  -d "{\"targets\":[\"all\"],\"items\":[{\"title\":\"新闻标题\",\"url\":\"https://example.com\",\"source\":\"sina\"}]}"

# Windows - 推送到指定目标
curl -X POST http://localhost:23120/push ^
  -H "Content-Type: application/json" ^
  -d "{\"targets\":[\"wechat_main\"],\"items\":[{\"title\":\"新闻标题\",\"url\":\"https://example.com\",\"source\":\"sina\"}]}"

# Windows - 空数组推送到全部
curl -X POST http://localhost:23120/push ^
  -H "Content-Type: application/json" ^
  -d "{\"targets\":[],\"items\":[{\"title\":\"新闻标题\",\"url\":\"https://example.com\",\"source\":\"sina\"}]}"

# macOS / Linux - 推送到全部目标
curl -X POST http://localhost:23120/push \
  -H "Content-Type: application/json" \
  -d '{"targets":["all"],"items":[{"title":"新闻标题","url":"https://example.com","source":"sina"}]}'

# macOS / Linux - 推送到指定目标
curl -X POST http://localhost:23120/push \
  -H "Content-Type: application/json" \
  -d '{"targets":["wechat_main"],"items":[{"title":"新闻标题","url":"https://example.com","source":"sina"}]}'
```

**响应：**

```json
{
  "status": "success",
  "target_type": "all",
  "success_count": 1,
  "failed_count": 0
}
```

---

### 完整使用流程

以下展示从采集到推送的完整流程：

```bash
# 1. 采集新闻数据
curl -X POST http://localhost:23119/collect \
  -H "Content-Type: application/json" \
  -d '{"sources":["sina"]}'

# 假设返回数据保存在 items.json 中

# 2. 将采集的数据推送到微信群
curl -X POST http://localhost:23120/push \
  -H "Content-Type: application/json" \
  -d '{
    "targets": ["wechat_main"],
    "items": [
      {"title": "新闻标题1", "url": "https://example.com/1", "source": "sina"},
      {"title": "新闻标题2", "url": "https://example.com/2", "source": "sina"}
    ]
  }'
```

## 测试指南

### 运行全部测试

```bash
python test.py
```

测试脚本会自动启动服务并执行全部测试用例。

### 测试内容

#### 采集服务测试

| 测试项     | 说明                         |
| ---------- | ---------------------------- |
| 健康检查   | 测试 `/collect/health` 接口  |
| 获取源列表 | 测试 `/collect/sources` 接口 |
| 采集全部   | 测试 `sources=["all"]`       |
| 空数组采集 | 测试 `sources=[]`            |
| 单源采集   | 测试 `sources=["sina"]`      |
| 多源采集   | 测试多个数据源               |
| 错误处理   | 测试不存在的源               |
| 并发控制   | 测试 `concurrency` 参数      |

#### 推送服务测试

| 测试项       | 说明                           |
| ------------ | ------------------------------ |
| 健康检查     | 测试 `/push/health` 接口       |
| 获取目标列表 | 测试 `/push/targets` 接口      |
| 全部推送     | 测试 `targets=["all"]`         |
| 空数组推送   | 测试 `targets=[]`              |
| 单目标推送   | 测试 `targets=["wechat_main"]` |
| 多目标推送   | 测试多个目标                   |
| 多条推送     | 测试推送多条数据               |
| 错误处理     | 测试不存在的目标               |

## 数据结构

### ParsedItem

采集结果的数据结构，用于在系统内部传递解析后的数据。

```python
@dataclass
class ParsedItem:
    title: str           # 新闻标题
    url: str            # 新闻链接
    source: Optional[str] = None  # 来源标识
```

### CollectRequest

采集请求的数据模型。

```python
class CollectRequest(BaseModel):
    sources: List[str]       # 要采集的数据源列表
    concurrency: int = 10    # 并发请求数
```

### CollectResponse

采集响应的数据模型。

```python
class CollectResponse(BaseModel):
    status: str                              # 状态：success / no_data / failed
    total_sources: int                       # 采集的源数量
    items_by_source: Dict[str, List[Dict]]  # 按源分组的采集结果
    total_items: int                         # 总数据条数
    errors: Optional[List[str]] = None       # 错误信息
```

### PushRequest

推送请求的数据模型。

```python
class PushRequest(BaseModel):
    items: List[Dict[str, Any]]  # 要推送的数据列表
    targets: List[str]           # 目标列表
```

### PushResponse

推送响应的数据模型。

```python
class PushResponse(BaseModel):
    status: str        # 状态：success / failed
    target_type: str   # 推送类型：all / batch
    success_count: int # 成功数
    failed_count: int  # 失败数
```

## 未来规划

NewsFlow 正在向更通用的数据管道框架演进。以下是计划中的功能：

### 数据处理层（已实现基础架构）

数据处理层已完成基础架构搭建，当前支持格式化功能，规划中的功能正在逐步实现。

### 已实现功能

- **数据格式化**：支持 markdown、text、plain 三种输出格式
- **处理链架构**：插件式处理器设计，支持链式处理

### 规划中功能

| 功能 | 状态 | 说明 |
| ---- | ---- | ---- |
| 去重 | 规划中 | 基于标题或 URL 去除重复数据 |
| 筛选 | 规划中 | 按关键词、来源等条件过滤数据 |
| 关键词提取 | 规划中 | 自动提取内容关键词 |
| 相似度对比 | 规划中 | 检测内容相似度，避免重复推送 |
| 推荐排序 | 规划中 | 基于规则的智能排序 |

### 架构演进

```
+------------------+     +------------------+     +------------------+
|   采集服务        | --> |   处理服务        | --> |   推送服务        |
|  (Collector)     |     |  (Processor)    |     |   (Pusher)       |
+------------------+     +------------------+     +------------------+
                              |
                  +-----------+-----------+
                  |  处理器插件注册表     |
                  |  - 去重处理器         |
                  |  - 筛选处理器         |
                  |  - 格式化处理器       |
                  +-----------------------+
```

### 扩展处理器指南

要添加新的处理器，只需实现 `BaseProcessor` 接口并注册到注册表：

```python
from processor import BaseProcessor, ProcessorRegistry

class MyProcessor(BaseProcessor):
    processor_type = "my_processor"

    async def process(self, data):
        # 处理逻辑
        return data

    def validate_config(self):
        return True

# 注册处理器
ProcessorRegistry.register("my_processor", MyProcessor)
```

## 许可证

本项目采用 MIT 许可证开源。
