"""
全局配置模块
定义 NewsFlow 项目的所有可配置参数，包括服务端口、HTTP 请求参数、推送目标等

使用示例：
from config import settings
print(settings.collector_port)  # 输出: 23119
"""


class Settings:
    """
    配置类，包含 NewsFlow 所有可配置的参数

    特点：
    - 使用类属性定义默认值，运行时可修改（在创建实例前）
    - 使用 @property 定义计算属性
    - 通过 settings 单例在项目中全局访问
    """

    # ========== 服务配置 ==========
    collector_host: str = "0.0.0.0"  # 采集服务监听地址，0.0.0.0 表示监听所有网卡
    collector_port: int = 23119  # 采集服务端口号
    pusher_host: str = "0.0.0.0"  # 推送服务监听地址
    pusher_port: int = 23120  # 推送服务端口号

    # ========== HTTP 请求配置 ==========
    timeout: float = 30.0  # HTTP 请求超时时间（秒），请求超过30秒则超时
    max_concurrency: int = 10  # 最大并发请求数，同时最多发起10个 HTTP 请求

    # ========== 服务间通信配置 ==========
    service_token: str = ""  # 服务间认证 Token，预留字段用于服务间安全通信
    default_role: str = "collector"  # 默认启动角色，不指定 --role 参数时的默认行为

    # ========== 推送目标配置 ==========
    # 字典键为自定义目标名称，值为目标配置
    # 支持多种推送平台：wechat（企业微信）、dingtalk（钉钉）、email（邮件）、qq（QQ）
    push_targets: dict = {
        "wechat_main": {
            "type": "wechat",  # 目标类型，对应 senders.py 中的发送器类
            "webhook_url": "",
        },
    }

    @property
    def pusher_service_url(self) -> str:
        """
        计算属性：获取推送服务的完整 URL 地址

        返回：
        str: 格式为 "http://host:port" 的 URL 字符串
        """
        return f"http://{self.pusher_host}:{self.pusher_port}"


settings = Settings()  # 创建 Settings 类的唯一实例，供整个项目使用
