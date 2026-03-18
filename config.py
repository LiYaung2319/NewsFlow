"""
全局配置模块
定义 NewsFlow 项目的所有可配置参数，包括服务端口、HTTP 请求参数、推送目标等

使用示例：
from config import settings
print(settings.collector_port)  # 输出: 23119
"""

from dotenv import load_dotenv  # 环境变量加载
import os  # 系统环境变量

load_dotenv()  # 加载 .env 文件中的配置


class Settings:
    host: str = "0.0.0.0"  # 服务监听地址
    port: int = 23119  # 服务端口号
    # collector_host: str = "0.0.0.0"  # 采集服务监听地址
    # collector_port: int = 23119  # 采集服务端口号
    # pusher_host: str = "0.0.0.0"  # 推送服务监听地址
    # pusher_port: int = 23120  # 推送服务端口号

    # ========== 浏览器请求配置 ==========
    browser_headless: bool = True  # 浏览器无头模式（不显示窗口）
    browser_timeout: float = 30.0  # 浏览器请求超时时间（秒）
    browser_wait_until: str = "load"  # 等待策略（load/domcontentloaded/networkidle）
    browser_wait_time: int = 0  # 额外等待时间（秒），等待动态内容
    max_concurrency: int = 3  # 最大并发页数（浏览器资源占用较大）

    # ========== 服务间通信配置 ==========
    service_token: str = ""  # 服务间认证 Token，预留字段用于服务间安全通信
    default_role: str = "collector"  # 默认启动角色，不指定 --role 参数时的默认行为

    # ========== 推送目标配置 ==========
    # 字典键为自定义目标名称，值为目标配置
    # 支持多种推送平台：wechat（企业微信）、dingtalk（钉钉）、email（邮件）、qq（QQ）
    push_targets: dict = {"wechat": os.environ.get("WECHAT_WEBHOOK_URL")}


settings = Settings()  # 创建 Settings 类的唯一实例，供整个项目使用
