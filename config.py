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
    browser_timeout: float = 60.0  # 浏览器请求超时时间（秒）
    browser_wait_until: str = "load"  # 等待策略（load/domcontentloaded/networkidle）
    browser_wait_time: int = 0  # 额外等待时间（秒），等待动态内容
    max_concurrency: int = 3  # 最大并发页数（浏览器资源占用较大）

    # 招聘源节流跨请求/进程持久化；预算不能通过请求参数放宽。
    jobs_request_interval: float = 12.0
    jobs_cache_ttl: int = 1800
    jobs_run_cooldown: int = 300
    jobs_block_cooldown: int = 1800
    jobs_response_timeout: int = 30000  # 毫秒
    auth_login_timeout: int = 300  # 来源登录任务最长等待秒数
    jobs_state_path: str = os.path.join(os.path.dirname(__file__), "data", "jobs_state.sqlite3")


settings = Settings()  # 创建 Settings 类的唯一实例，供整个项目使用
