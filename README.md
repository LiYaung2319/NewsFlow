# NewsFlow

NewsFlow 是一个轻量级新闻采集、格式化和 Webhook 推送服务。项目采用模块化单体架构：采集、处理和推送功能运行在同一个 FastAPI/Uvicorn 进程中，通过 HTTP 接口提供能力。

项目本身不包含数据库、消息队列或定时任务。完整的新闻工作流由外部调用方按顺序编排：

```text
POST /collect
      |
      v
采集结果 items_by_source
      |
      v
POST /processor/format
      |
      v
Markdown 消息列表 messages
      |
      v
POST /push
      |
      v
企业微信 / WPS Webhook
```

## 架构

```text
main.py
├── collector/
│   ├── services.py        采集 API 和采集流程编排
│   ├── browser_client.py  Playwright 异步浏览器客户端
│   └── parser.py          信息源解析器和注册表
├── processor/
│   ├── services.py        格式化 API
│   ├── formatter.py       Markdown 格式化器
│   └── __init__.py
├── pusher/
│   ├── services.py        推送 API 和推送目标编排
│   └── senders.py         各平台 Webhook 推送器
├── schemas.py             Pydantic 请求/响应模型和 ParsedItem
└── config.py              服务及浏览器默认配置
```

### 接入层

[`main.py`](main.py) 创建 FastAPI 应用，并注册以下三个路由组：

- `/collect/*`：新闻采集
- `/processor/*`：数据格式化
- `/push/*`：消息推送

### 采集层

采集服务使用 [`BrowserClient`](collector/browser_client.py) 通过 Playwright Chromium 获取页面内容，再交给 [`BaseParser`](collector/parser.py) 的具体实现解析。

- 单个普通信息源使用串行采集
- 多个信息源使用 `asyncio.gather()` 并发采集
- 复合信息源（如 `aihot`、`CSDN`）展开后的页面使用批量采集
- 使用信号量限制浏览器页面并发数
- 单个页面失败时保留其它页面的采集结果

### 处理层

[`CollectFormatter`](processor/formatter.py) 将 `items_by_source` 转换为 Markdown 消息列表。每个结果键单独生成消息，内容长度超过 2000 个字符后按条目分块；分块是在追加完整条目后判断，因此单个块可能略微超过 2000 个字符。

### 推送层

推送服务根据目标选择对应的 [`BaseSender`](pusher/senders.py) 实现，通过 HTTPX 调用平台 Webhook。

- 单个目标：目标内部按消息顺序推送
- 多个目标：不同目标之间并发推送

## 信息源

当前共有 5 个逻辑信息源：

| 标识 | 网站 | 采集内容 |
| --- | --- | --- |
| `sina` | 新浪新闻 | 新闻首页列表 |
| `163` | 网易新闻 | 网易首页新闻列表 |
| `tencent` | 腾讯新闻 | 腾讯新闻首页列表 |
| `aihot` | [AIHOT](https://aihot.virxact.com/) | AI 热点榜和今日 AI 日报 |
| `CSDN` | [CSDN](https://www.csdn.net/) | 资讯头条、人工智能和 Python |

### AIHOT 复合信息源

`aihot` 对外是一个信息源，但实际会采集两个页面：

| 内部结果键 | 页面 | 链接类型 | 展示标题 |
| --- | --- | --- | --- |
| `aihot_hot` | `/hot` | `/story/...` | AI 热点榜 |
| `aihot_daily` | `/daily` | `/items/...` | AI 日报 |

`/hot` 只提取当前热点榜事件；`/daily` 只提取当日日报正文事件，不会提取历史日报导航链接。两个板块分别返回、分别格式化、分别推送。

信息源解析器和注册表位于 [`collector/parser.py`](collector/parser.py)：

- `SinaParser`
- `NeteaseParser`
- `TencentParser`
- `AihotParser(section="hot")`
- `AihotParser(section="daily")`
- `CsdnParser(section="all")`
- `CsdnParser(section="ai")`
- `CsdnParser(section="python")`

### CSDN 复合信息源

`CSDN` 对外是一个信息源，内部拆分为三个独立结果键：

| 内部结果键 | 内容 | 采集方式 |
| --- | --- | --- |
| `CSDN_all` | 全部栏目下的资讯头条全部内容 | CSDN 首页 HTML |
| `CSDN_ai` | 人工智能栏目按接口顺序前 10 条 | CSDN 内容接口，参数 `cate1=ai` |
| `CSDN_python` | Python 栏目按接口顺序前 10 条 | CSDN 内容接口，参数 `cate1=python` |

三个板块分别采集、分别返回、分别格式化，不会合并为一组消息。

`CSDN_all` 当前从首页 `资讯头条` 区域提取顶部推荐和头条列表中的所有标题、链接；`CSDN_ai` 和 `CSDN_python` 从 CSDN 内容接口的 `extend.title`、`extend.url` 字段提取前 10 条。

## 推送目标

当前共有 2 个推送目标：

| 标识 | 平台 | 环境变量 |
| --- | --- | --- |
| `wechat` | 企业微信机器人 Webhook | `WECHAT_WEBHOOK_URL` |
| `wps` | WPS 协作 Webhook | `WPS_WEBHOOK_URL` |

推送器注册表位于 [`pusher/senders.py`](pusher/senders.py)。没有配置对应 Webhook 时，该目标会被标记为未启用。

## API

### 采集服务

```text
GET  /collect/sources
GET  /collect/health
POST /collect
```

`POST /collect` 请求体：

```json
{
  "sources": ["sina", "163"],
  "concurrency": 3
}
```

说明：

- `sources` 为空或包含 `all` 时采集全部逻辑信息源
- `concurrency` 可选；未提供时使用配置中的默认值 3
- 请求 `aihot` 时，会同时采集 `/hot` 和 `/daily`
- 请求 `CSDN` 时，会同时采集 `CSDN_all`、`CSDN_ai` 和 `CSDN_python`
- 复合信息源会展开为多个内部结果键，但响应中的 `total_sources` 仍按请求中的逻辑信息源数量统计；例如请求 `CSDN` 时为 1
- 未注册的信息源不会进入采集页面配置；批量采集时会返回其它有效配置的结果

采集示例：

```bash
curl -X POST http://localhost:23119/collect \
  -H "Content-Type: application/json" \
  -d '{"sources": ["aihot"]}'
```

采集 CSDN 三个独立板块：

```bash
curl -X POST http://localhost:23119/collect \
  -H "Content-Type: application/json" \
  -d '{"sources": ["CSDN"]}'
```

响应结果中的 `items_by_source` 会包含类似结构：

```json
{
  "aihot_hot": [
    {
      "title": "热点标题",
      "url": "https://aihot.virxact.com/story/...",
      "source": "aihot_hot"
    }
  ],
  "aihot_daily": [
    {
      "title": "日报标题",
      "url": "https://aihot.virxact.com/items/...",
      "source": "aihot_daily"
    }
  ]
}
```

请求 CSDN 时，响应中的 `items_by_source` 结构如下：

```json
{
  "CSDN_all": [
    {
      "title": "资讯头条标题",
      "url": "https://blog.csdn.net/...",
      "source": "CSDN_all"
    }
  ],
  "CSDN_ai": [
    {
      "title": "人工智能文章标题",
      "url": "https://blog.csdn.net/...",
      "source": "CSDN_ai"
    }
  ],
  "CSDN_python": [
    {
      "title": "Python 文章标题",
      "url": "https://blog.csdn.net/...",
      "source": "CSDN_python"
    }
  ]
}
```

### 处理服务

```text
GET  /processor/health
POST /processor/format
```

`POST /processor/format` 接收一个格式化任务列表。当前支持的格式化类型只有 `collect`：

```bash
curl -X POST http://localhost:23119/processor/format \
  -H "Content-Type: application/json" \
  -d '{"data": [{"collect": {"aihot_hot": [{"title": "热点标题", "url": "https://aihot.virxact.com/story/..."}], "aihot_daily": [{"title": "日报标题", "url": "https://aihot.virxact.com/items/..."}]}}]}'
```

AIHOT 格式化后会生成两条消息，标题分别为：

```markdown
# AI 热点榜
...
```

```markdown
# AI 日报
...
```

### 推送服务

```text
GET  /push/targets
GET  /push/health
POST /push
```

`POST /push` 请求体：

```json
{
  "items": [
    "# AI 热点榜\n- [热点标题](https://aihot.virxact.com/story/...)",
    "# AI 日报\n- [日报标题](https://aihot.virxact.com/items/...)"
  ],
  "targets": ["wechat"]
}
```

说明：

- `targets` 为空或包含 `all` 时推送到全部已注册目标
- 每个字符串视为一条独立消息
- `success_count` 和 `failed_count` 按实际发送的消息数量统计

## 配置

配置模块为 [`config.py`](config.py)，当前默认值如下：

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `settings.host` | `0.0.0.0` | 服务监听地址 |
| `settings.port` | `23119` | 服务端口 |
| `settings.browser_headless` | `True` | 是否使用无头浏览器 |
| `settings.browser_timeout` | `60.0` | 页面访问超时时间，单位为秒 |
| `settings.browser_wait_until` | `load` | Playwright 页面等待策略 |
| `settings.browser_wait_time` | `0` | 页面加载后的额外等待时间，单位为秒 |
| `settings.max_concurrency` | `3` | 默认最大并发页面数 |

项目会通过 `python-dotenv` 加载根目录 `.env` 文件。当前 `.env` 仅用于推送 Webhook：

```env
WECHAT_WEBHOOK_URL=your_wechat_webhook_url
WPS_WEBHOOK_URL=your_wps_webhook_url
```

服务地址和浏览器配置目前由 [`config.py`](config.py) 中的默认值定义，并不会自动从环境变量读取。

## 安装和运行

### 安装依赖

```bash
pip install -r requirements.txt
playwright install chromium
```

### 直接运行

```bash
python main.py
```

该方式使用 `settings.host` 和 `settings.port` 启动 Uvicorn，并开启热重载。

### 使用 Uvicorn

```bash
uvicorn main:app --host 0.0.0.0 --port 23119 --reload
```

### Windows 脚本

```text
start.bat  后台启动服务，日志写入 logs/output.log 和 logs/error.log
stop.bat   终止 python.exe 进程
```

`stop.bat` 会终止当前机器上所有名为 `python.exe` 的进程，请谨慎使用。

## 技术栈

- Python
- FastAPI
- Uvicorn
- Playwright
- parsel
- Pydantic
- HTTPX
- python-dotenv

当前项目未包含自动化测试、数据库、任务队列、容器配置或 CI/CD 配置。采集、格式化和推送也不会在服务内部自动串联，调用方需要分别调用对应接口。
