#!/usr/bin/env python3
"""
NewsFlow 服务接口测试脚本
一键检测采集和推送服务全部接口
"""

import asyncio
import aiohttp
import time
import sys
import json
import subprocess
from typing import Optional, Dict, Any
from pathlib import Path

# 配置
BASE_DIR = Path(__file__).parent
COLLECTOR_URL = "http://localhost:23119"
PUSHER_URL = "http://localhost:23120"
SERVICES = {
    "collector": {"port": 23119, "name": "采集服务"},
    "pusher": {"port": 23120, "name": "推送服务"}
}

# 当前可用的采集源
AVAILABLE_SOURCES = ["sina"]


def kill_port_process(port: int) -> bool:
    """查找并终止占用指定端口的进程"""
    print(f"🔍 检查端口 {port} 是否被占用...")
    
    try:
        result = subprocess.run(
            f'netstat -ano | findstr :{port}',
            shell=True,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"   端口 {port} 未被占用")
            return True
        
        lines = result.stdout.strip().split('\n')
        pids = set()
        
        for line in lines:
            if 'LISTENING' in line:
                parts = line.split()
                if len(parts) >= 5:
                    pid = parts[-1]
                    if pid.isdigit():
                        pids.add(pid)
        
        if not pids:
            print(f"   端口 {port} 未被占用")
            return True
        
        for pid in pids:
            try:
                print(f"   终止进程 PID={pid}...")
                subprocess.run(f'taskkill /PID {pid} /F', shell=True, capture_output=True)
                print(f"   ✅ 进程 {pid} 已终止")
            except Exception:
                pass
        
        time.sleep(1)
        print(f"   端口 {port} 已释放")
        return True
        
    except Exception as e:
        print(f"   ❌ 检查端口失败: {e}")
        return False


def stop_services():
    """停止可能占用端口的服务"""
    print("\n🛑 检查并停止可能占用端口的服务...")
    print("=" * 50)
    
    for name, config in SERVICES.items():
        kill_port_process(config["port"])
    
    print("=" * 50)


class ServiceManager:
    """服务管理器"""
    
    def __init__(self):
        self.processes = {}
    
    def start_service(self, role: str) -> bool:
        """启动服务"""
        config = SERVICES[role]
        name = config["name"]
        port = config["port"]
        
        print(f"🚀 启动 {name} (端口 {port})...")
        
        try:
            cmd = [sys.executable, str(BASE_DIR / "main.py"), "--role", role]
            
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    startupinfo=startupinfo
                )
            else:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
            
            self.processes[role] = process
            print(f"   ✅ {name} 进程已启动 (PID={process.pid})")
            return True
            
        except Exception as e:
            print(f"   ❌ 启动 {name} 失败: {e}")
            return False
    
    def stop_all(self):
        """停止所有服务"""
        print("\n🛑 停止所有测试服务...")
        for role, process in self.processes.items():
            try:
                name = SERVICES[role]["name"]
                print(f"   终止 {name} (PID={process.pid})...")
                process.terminate()
                process.wait(timeout=5)
                print(f"   ✅ {name} 已停止")
            except Exception:
                try:
                    process.kill()
                except:
                    pass
        
        self.processes.clear()


class NewsFlowTester:
    """NewsFlow 服务测试器"""
    
    def __init__(self):
        self.collector_data = None
        self.service_manager = ServiceManager()
    
    async def wait_for_service(self, url: str, name: str, timeout: int = 30) -> bool:
        """等待服务启动"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{url}/push/health", timeout=aiohttp.ClientTimeout(total=3)) as resp:
                        if resp.status == 200:
                            print(f"✅ {name} 已就绪")
                            return True
            except Exception:
                pass
            time.sleep(1)
        
        print(f"❌ {name} 启动超时")
        return False
    
    async def test_collector_health(self) -> dict:
        """测试采集服务健康检查"""
        print("\n" + "=" * 50)
        print("📥 测试采集服务健康检查")
        print("=" * 50)
        
        url = f"{COLLECTOR_URL}/collect/health"
        result = await self._request("GET", url)
        
        self._print_result("GET /collect/health", result)
        return result
    
    async def test_collector_sources(self) -> dict:
        """测试获取可用源列表"""
        print("\n" + "=" * 50)
        print("📋 测试获取可用源列表")
        print("=" * 50)
        
        url = f"{COLLECTOR_URL}/collect/sources"
        result = await self._request("GET", url)
        
        self._print_result("GET /collect/sources", result)
        return result
    
    async def test_collector_all_sources(self) -> dict:
        """测试采集全部源"""
        print("\n" + "=" * 50)
        print("🌐 测试采集全部源 (sources=[\"all\"])")
        print("=" * 50)
        
        url = f"{COLLECTOR_URL}/collect"
        payload = {"sources": ["all"]}
        result = await self._request("POST", url, payload)
        
        self._print_result("POST /collect (all)", result)
        return result
    
    async def test_collector_empty_sources(self) -> dict:
        """测试空数组采集全部"""
        print("\n" + "=" * 50)
        print("🌐 测试采集全部源 (sources=[])")
        print("=" * 50)
        
        url = f"{COLLECTOR_URL}/collect"
        payload = {"sources": []}
        result = await self._request("POST", url, payload)
        
        self._print_result("POST /collect (empty)", result)
        return result
    
    async def test_collector_single_source(self) -> dict:
        """测试采集单个源"""
        print("\n" + "=" * 50)
        print("📰 测试采集单个源 (sources=[\"sina\"])")
        print("=" * 50)
        
        url = f"{COLLECTOR_URL}/collect"
        payload = {"sources": ["sina"]}
        result = await self._request("POST", url, payload)
        
        self._print_result("POST /collect (sina)", result)
        return result
    
    async def test_collector_multiple_sources(self) -> dict:
        """测试采集多个源"""
        print("\n" + "=" * 50)
        print(f"📰 测试采集多个源 (sources={AVAILABLE_SOURCES})")
        print("=" * 50)
        
        url = f"{COLLECTOR_URL}/collect"
        payload = {"sources": AVAILABLE_SOURCES}
        result = await self._request("POST", url, payload)
        
        self._print_result(f"POST /collect ({AVAILABLE_SOURCES})", result)
        return result
    
    async def test_collector_invalid_source(self) -> dict:
        """测试采集不存在的源"""
        print("\n" + "=" * 50)
        print("❌ 测试采集不存在的源")
        print("=" * 50)
        
        url = f"{COLLECTOR_URL}/collect"
        payload = {"sources": ["invalid_source"]}
        result = await self._request("POST", url, payload, expect_error=True)
        
        self._print_result("POST /collect (invalid)", result, expect_error=True)
        return result
    
    async def test_collector_concurrency(self) -> dict:
        """测试并发参数"""
        print("\n" + "=" * 50)
        print("⚡ 测试并发参数控制")
        print("=" * 50)
        
        url = f"{COLLECTOR_URL}/collect"
        payload = {"sources": ["sina"], "concurrency": 5}
        result = await self._request("POST", url, payload)
        
        self._print_result("POST /collect (concurrency=5)", result)
        return result
    
    async def test_pusher_health(self) -> dict:
        """测试推送服务健康检查"""
        print("\n" + "=" * 50)
        print("📤 测试推送服务健康检查")
        print("=" * 50)
        
        url = f"{PUSHER_URL}/push/health"
        result = await self._request("GET", url)
        
        self._print_result("GET /push/health", result)
        return result
    
    async def test_pusher_targets(self) -> dict:
        """测试获取可用目标列表"""
        print("\n" + "=" * 50)
        print("📋 测试获取可用目标列表")
        print("=" * 50)
        
        url = f"{PUSHER_URL}/push/targets"
        result = await self._request("GET", url)
        
        self._print_result("GET /push/targets", result)
        return result
    
    async def test_pusher_all_targets(self) -> dict:
        """测试推送到全部目标"""
        print("\n" + "=" * 50)
        print("🚀 测试推送到全部目标 (targets=[\"all\"])")
        print("=" * 50)
        
        items = self._get_test_items()
        url = f"{PUSHER_URL}/push"
        payload = {"targets": ["all"], "items": items}
        result = await self._request("POST", url, payload)
        
        self._print_result("POST /push (all)", result)
        return result
    
    async def test_pusher_empty_targets(self) -> dict:
        """测试空数组推送到全部"""
        print("\n" + "=" * 50)
        print("🚀 测试推送到全部目标 (targets=[])")
        print("=" * 50)
        
        items = self._get_test_items()
        url = f"{PUSHER_URL}/push"
        payload = {"targets": [], "items": items}
        result = await self._request("POST", url, payload)
        
        self._print_result("POST /push (empty)", result)
        return result
    
    async def test_pusher_single_target(self) -> dict:
        """测试推送到单个目标"""
        print("\n" + "=" * 50)
        print("🎯 测试推送到单个目标 (targets=[\"wechat_main\"])")
        print("=" * 50)
        
        items = self._get_test_items()
        url = f"{PUSHER_URL}/push"
        payload = {"targets": ["wechat_main"], "items": items}
        result = await self._request("POST", url, payload)
        
        self._print_result("POST /push (wechat_main)", result)
        return result
    
    async def test_pusher_batch_targets(self) -> dict:
        """测试批量推送"""
        print("\n" + "=" * 50)
        print("📨 测试批量推送 (targets=[\"wechat_main\"])")
        print("=" * 50)
        
        items = self._get_test_items()
        url = f"{PUSHER_URL}/push"
        payload = {"targets": ["wechat_main"], "items": items}
        result = await self._request("POST", url, payload)
        
        self._print_result("POST /push (batch)", result)
        return result
    
    async def test_pusher_multiple_items(self) -> dict:
        """测试推送多条新闻"""
        print("\n" + "=" * 50)
        print("📃 测试推送多条新闻")
        print("=" * 50)
        
        items = self._get_multiple_test_items()
        url = f"{PUSHER_URL}/push"
        payload = {"targets": ["wechat_main"], "items": items}
        result = await self._request("POST", url, payload)
        
        self._print_result("POST /push (multiple items)", result)
        return result
    
    async def test_pusher_invalid_target(self) -> dict:
        """测试推送到不存在的目标"""
        print("\n" + "=" * 50)
        print("❌ 测试推送到不存在的目标")
        print("=" * 50)
        
        items = self._get_test_items()
        url = f"{PUSHER_URL}/push"
        payload = {"targets": ["invalid_target"], "items": items}
        result = await self._request("POST", url, payload, expect_error=True)
        
        self._print_result("POST /push (invalid)", result, expect_error=True)
        return result
    
    def _get_test_items(self) -> list:
        """获取测试数据"""
        if self.collector_data and self.collector_data.get("items_by_source"):
            items = []
            for source, source_items in self.collector_data["items_by_source"].items():
                for item in source_items[:3]:
                    items.append(item)
            if items:
                return items
        return [{"title": "测试新闻标题", "url": "https://example.com/news/1", "source": "test"}]
    
    def _get_multiple_test_items(self) -> list:
        """获取多条测试数据"""
        return [
            {"title": "新闻标题1", "url": "https://example.com/1", "source": "sina"},
            {"title": "新闻标题2", "url": "https://example.com/2", "source": "163"},
            {"title": "新闻标题3", "url": "https://example.com/3", "source": "tencent"},
            {"title": "新闻标题4", "url": "https://example.com/4", "source": "sina"},
            {"title": "新闻标题5", "url": "https://example.com/5", "source": "sina"},
        ]
    
    async def _request(self, method: str, url: str, data: Optional[Dict[str, Any]] = None, expect_error: bool = False) -> Dict[str, Any]:
        """发起 HTTP 请求"""
        try:
            async with aiohttp.ClientSession() as session:
                kwargs = {"timeout": aiohttp.ClientTimeout(total=30)}
                if data:
                    kwargs["json"] = data
                    kwargs["headers"] = {"Content-Type": "application/json"}
                
                if method == "GET":
                    async with session.get(url, **kwargs) as resp:
                        text = await resp.text()
                        try:
                            result = json.loads(text)
                        except:
                            result = {"raw": text}
                        result["_status_code"] = resp.status
                        return result
                else:
                    async with session.post(url, **kwargs) as resp:
                        text = await resp.text()
                        try:
                            result = json.loads(text)
                        except:
                            result = {"raw": text}
                        result["_status_code"] = resp.status
                        return result
        except Exception as e:
            return {"error": str(e), "_status_code": -1}
    
    def _print_result(self, name: str, result: Dict[str, Any], expect_error: bool = False):
        """打印测试结果"""
        status_code = result.get("_status_code", -1)
        
        if expect_error:
            if status_code in [400, 404, -1] or "error" in result or "detail" in result:
                print(f"✅ {name}: 正确触发错误响应")
                print(f"   状态码: {status_code}")
            else:
                print(f"⚠️ {name}: 期望错误但未触发")
        else:
            if status_code == 200:
                print(f"✅ {name}: 成功")
            else:
                print(f"❌ {name}: 失败 (状态码: {status_code})")
        
        print(f"   返回内容:")
        print(f"   {json.dumps(result, ensure_ascii=False, indent=4)}")
    
    async def run_all_tests(self):
        """运行全部测试"""
        print("\n" + "#" * 60)
        print("#" + " " * 15 + "NewsFlow 服务接口测试" + " " * 16 + "#")
        print("#" * 60)
        
        # 停止可能占用端口的服务
        stop_services()
        
        # 启动服务
        print("\n🚀 启动服务...")
        print("=" * 50)
        
        self.service_manager.start_service("collector")
        self.service_manager.start_service("pusher")
        
        print("=" * 50)
        
        # 等待服务启动
        print("\n⏳ 等待服务启动...")
        time.sleep(2)
        
        await self.wait_for_service(COLLECTOR_URL, SERVICES["collector"]["name"])
        await self.wait_for_service(PUSHER_URL, SERVICES["pusher"]["name"])
        
        # 采集服务测试
        print("\n" + "🧪 " + "=" * 48)
        print("🧪 " + " " * 18 + "采集服务测试" + " " * 18)
        print("🧪 " + "=" * 48)
        
        await self.test_collector_health()
        await self.test_collector_sources()
        
        print("\n🔄 采集数据用于推送测试...")
        self.collector_data = await self.test_collector_all_sources()
        
        await self.test_collector_empty_sources()
        await self.test_collector_single_source()
        await self.test_collector_multiple_sources()
        await self.test_collector_invalid_source()
        await self.test_collector_concurrency()
        
        # 推送服务测试
        print("\n" + "🧪 " + "=" * 48)
        print("🧪 " + " " * 18 + "推送服务测试" + " " * 18)
        print("🧪 " + "=" * 48)
        
        await self.test_pusher_health()
        await self.test_pusher_targets()
        await self.test_pusher_all_targets()
        await self.test_pusher_empty_targets()
        await self.test_pusher_single_target()
        await self.test_pusher_batch_targets()
        await self.test_pusher_multiple_items()
        await self.test_pusher_invalid_target()
        
        # 停止服务
        self.service_manager.stop_all()
        
        # 总结
        print("\n" + "#" * 60)
        print("#" + " " * 20 + "测试完成" + " " * 23 + "#")
        print("#" * 60)


async def main():
    """主函数"""
    tester = NewsFlowTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断测试")
        sys.exit(0)
