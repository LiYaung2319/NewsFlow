"""
全局配置模块
定义 NewsFlow 项目的可配置参数

使用示例：
from config import settings
print(settings.port)  # 输出: 23119
"""

from dotenv import load_dotenv
import os

load_dotenv()  # 加载 .env 文件中的配置


class Settings:
    """项目配置"""

    host: str = "0.0.0.0"  # 服务监听地址
    port: int = 23119  # 服务端口号

    # ==================== 浏览器请求配置 ====================
    browser_headless: bool = True  # 浏览器无头模式（不显示窗口）
    browser_timeout: float = 30.0  # 浏览器请求超时时间（秒）
    browser_wait_until: str = "load"  # 等待策略（load/domcontentloaded/networkidle）
    browser_wait_time: int = 0  # 额外等待时间（秒），等待动态内容
    max_concurrency: int = 3  # 最大并发页数（浏览器资源占用较大）


settings = Settings()  # 创建 Settings 类的唯一实例，供整个项目使用
