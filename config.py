class Settings:
    collector_host: str = "0.0.0.0"
    collector_port: int = 23119
    pusher_host: str = "0.0.0.0"
    pusher_port: int = 23120
    timeout: float = 30.0
    max_concurrency: int = 10
    service_token: str = ""
    default_role: str = "pusher"

    push_targets: dict = {
        "wechat_main": {
            "type": "wechat",
            "webhook_url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=48839e8e-6a87-42ee-9d7a-b55bd181a52b",
        }
    }

    @property
    def pusher_service_url(self) -> str:
        return f"http://{self.pusher_host}:{self.pusher_port}"


settings = Settings()
