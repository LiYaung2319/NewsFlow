import uvicorn
import argparse
import sys
from services.collector import app as collector_app
from services.pusher import app as pusher_app
from config import settings


def parse_args():
    parser = argparse.ArgumentParser(
        description="NewsFlow - News Collection & Push Service",
        epilog="Services:\n"
               "  collector  - News collection service (port 23119)\n"
               "  pusher     - Message push service (port 23120)"
    )
    parser.add_argument(
        "--role",
        type=str,
        choices=["collector", "pusher"],
        default=settings.default_role,
        help="Service role: collector (port 23119) or pusher (port 23120)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    role = args.role
    print(f"[Config] 使用角色: {role}")

    if role == "collector":
        uvicorn.run(
            collector_app,
            host=settings.collector_host,
            port=settings.collector_port,
        )
    else:
        uvicorn.run(
            pusher_app,
            host=settings.pusher_host,
            port=settings.pusher_port,
        )


if __name__ == "__main__":
    main()
