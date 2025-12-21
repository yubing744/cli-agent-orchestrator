#!/usr/bin/env python3
"""
CAO Agent Orchestrator Bridge
CLI工具，简化CAO API的使用和Agent管理
"""

import asyncio
import json
import sys
import time
import warnings
from typing import Dict, List, Optional, Any

# Suppress urllib3 v2 LibreSSL warning on macOS Python builds.
warnings.filterwarnings(
    "ignore",
    message=r"urllib3 v2 only supports OpenSSL 1\.1\.1\+.*",
)

import requests
import argparse
import subprocess
import threading
import time
import os
from pathlib import Path

# CAO API配置
CAO_API_BASE = "http://localhost:9889"
CAO_TEST_REPO = "https://github.com/yubing744/cli-agent-orchestrator.git"
CAO_TEST_BRANCH = "test"

class CaoBridge:
    """CAO API Bridge客户端"""

    def __init__(self, base_url: str = CAO_API_BASE):
        self.base_url = base_url
        self.session = requests.Session()

    def _install_uvx_if_needed(self) -> bool:
        """检查并安装uvx"""
        try:
            subprocess.run(["uvx", "--version"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("📦 uvx not found, installing...")
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", "uvx"], check=True)
                print("✅ uvx installed successfully")
                return True
            except subprocess.CalledProcessError:
                print("❌ Failed to install uvx")
                return False

    def _install_cao_with_uvx(self) -> bool:
        """使用uvx安装测试版本CAO"""
        if not self._install_uvx_if_needed():
            return False

        print("🚀 Installing CAO test version using uvx...")

        # 首先检查能否访问仓库
        try:
            import subprocess
            result = subprocess.run([
                "git", "ls-remote", f"{CAO_TEST_REPO}", CAO_TEST_BRANCH
            ], capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                print(f"❌ Cannot access CAO repository: {CAO_TEST_REPO}")
                print(f"   Error: {result.stderr}")
                return False
            print("✅ CAO repository is accessible")
        except Exception as e:
            print(f"❌ Failed to access CAO repository: {e}")
            return False

        try:
            # 使用uvx安装CAO测试版本
            cmd = [
                "uvx",
                "--from", f"git+{CAO_TEST_REPO}@{CAO_TEST_BRANCH}",
                "cao",
                "api", "--host", "localhost", "--port", "9889"
            ]

            print(f"Running: {' '.join(cmd)}")
            print("⚠️ This may take a few minutes for the first installation...")

            # 在后台启动CAO服务
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=dict(os.environ, UV_INDEX_URL="https://pypi.org/simple/")  # 确保使用官方PyPI
            )

            # 等待服务启动，增加等待时间
            print("⏳ Waiting for CAO service to start...")
            max_wait = 120  # 增加到120秒
            for i in range(max_wait):
                # 检查进程是否还在运行
                if process.poll() is not None:
                    stdout, stderr = process.communicate()
                    print(f"❌ CAO process exited early (return code: {process.returncode})")
                    if stdout:
                        print(f"Stdout: {stdout[-500:]}")  # 只显示最后500字符
                    if stderr:
                        print(f"Stderr: {stderr[-500:]}")
                    return False

                # 直接检查服务状态，不触发自动安装
                try:
                    response = self.session.get(f"{self.base_url}/health", timeout=5)
                    if response.status_code == 200:
                        print("✅ CAO service started successfully")
                        return True
                except Exception:
                    pass

                time.sleep(1)
                if i % 10 == 0:
                    print(f"   Still waiting... ({i}/{max_wait} seconds)")

            # 如果超时，检查进程状态
            if process.poll() is None:
                print("⚠️ CAO process is still running but not responding to health checks")
                print("   This might be normal if the service is still starting up")
                print("   You can check manually with: curl http://localhost:9889/health")
                # 不要终止进程，让它在后台继续运行
                return True  # 认为安装成功，即使还没完全启动
            else:
                stdout, stderr = process.communicate()
                print(f"❌ CAO process exited after timeout")
                if stdout:
                    print(f"Stdout: {stdout[-500:]}")
                if stderr:
                    print(f"Stderr: {stderr[-500:]}")

            return False

        except subprocess.TimeoutExpired:
            print("❌ Installation timeout - network issues or dependency problems")
            return False
        except Exception as e:
            print(f"❌ Failed to install/run CAO with uvx: {e}")
            return False

    def health_check(self) -> bool:
        """检查CAO服务健康状态"""
        try:
            response = self.session.get(f"{self.base_url}/health")
            return response.status_code == 200
        except Exception:
            return False

    def install_cao_if_needed(self) -> bool:
        """检查并安装CAO服务（如果需要）"""
        if self.health_check():
            print("✅ CAO service is already running")
            return True

        print("❌ CAO service is not available, attempting auto-install...")
        return self._install_cao_with_uvx()

    def list_sessions(self) -> List[Dict]:
        """列出所有sessions"""
        try:
            response = self.session.get(f"{self.base_url}/sessions")
            if response.status_code == 200:
                return response.json()
            return []
        except Exception as e:
            print(f"Error listing sessions: {e}")
            return []

    def create_session(
        self,
        agent_profile: str,
        session_name: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> Dict:
        """创建新的session"""
        try:
            params: Dict[str, str] = {"agent_profile": agent_profile}
            if session_name:
                params["session_name"] = session_name

            if provider:
                params["provider"] = provider

            response = self.session.post(f"{self.base_url}/sessions", params=params)
            if response.status_code in [200, 201]:  # 201 Created也是成功
                return response.json()
            else:
                print(f"Error creating session: {response.status_code}")
                print(f"Response: {response.text}")
                return {}
        except Exception as e:
            print(f"Error creating session: {e}")
            return {}

    def create_session_with_provider(
        self,
        agent_profile: str,
        provider: Optional[str] = None,
        session_name: Optional[str] = None,
    ) -> Dict:
        """创建新的session（可选指定provider）"""
        return self.create_session(agent_profile=agent_profile, session_name=session_name, provider=provider)

    def get_session_terminals(self, session_name: str) -> List[Dict]:
        """获取session中的terminals"""
        try:
            response = self.session.get(f"{self.base_url}/sessions/{session_name}/terminals")
            if response.status_code == 200:
                return response.json()
            return []
        except Exception as e:
            print(f"Error getting terminals: {e}")
            return []

    def get_terminal(self, terminal_id: str) -> Dict:
        """获取terminal信息"""
        try:
            response = self.session.get(f"{self.base_url}/terminals/{terminal_id}")
            if response.status_code == 200:
                return response.json()
            return {}
        except Exception as e:
            print(f"Error getting terminal: {e}")
            return {}

    def get_terminal_output(self, terminal_id: str, mode: str = "full") -> str:
        """获取terminal输出"""
        try:
            params = {"mode": mode}
            response = self.session.get(f"{self.base_url}/terminals/{terminal_id}/output", params=params)
            if response.status_code == 200:
                return response.json().get("output", "")
            return ""
        except Exception as e:
            print(f"Error getting terminal output: {e}")
            return ""

    def send_terminal_input(self, terminal_id: str, message: str) -> bool:
        """向terminal发送消息"""
        try:
            params = {"message": message}
            response = self.session.post(f"{self.base_url}/terminals/{terminal_id}/input", params=params)
            return response.status_code == 200
        except Exception as e:
            print(f"Error sending terminal input: {e}")
            return False

    def delete_terminal(self, terminal_id: str) -> bool:
        """删除terminal"""
        try:
            response = self.session.delete(f"{self.base_url}/terminals/{terminal_id}")
            return response.status_code == 200
        except Exception as e:
            print(f"Error deleting terminal: {e}")
            return False

    def get_inbox_messages(
        self,
        terminal_id: str,
        limit: int = 20,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """获取terminal inbox消息（如果CAO支持该端点）"""
        try:
            params: Dict[str, Any] = {"limit": limit}
            if status:
                params["status"] = status

            response = self.session.get(
                f"{self.base_url}/terminals/{terminal_id}/inbox/messages",
                params=params,
            )
            if response.status_code == 200:
                data = response.json()
                # Some implementations return {"messages": [...]}.
                if isinstance(data, dict) and "messages" in data and isinstance(data["messages"], list):
                    return data["messages"]
                if isinstance(data, list):
                    return data
                return []

            print(f"Error getting inbox messages: {response.status_code}")
            print(f"Response: {response.text}")
            return []
        except Exception as e:
            print(f"Error getting inbox messages: {e}")
            return []

    def send_inbox_message(
        self,
        receiver_id: str,
        sender_id: str,
        message: str,
    ) -> bool:
        """向terminal发送inbox消息（如果CAO支持该端点）"""
        try:
            # Prefer JSON body; fallback to query params for older implementations
            payload = {"sender_id": sender_id, "message": message}
            response = self.session.post(
                f"{self.base_url}/terminals/{receiver_id}/inbox/messages",
                json=payload,
            )
            if response.status_code == 200:
                return True

            response = self.session.post(
                f"{self.base_url}/terminals/{receiver_id}/inbox/messages",
                params=payload,
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Error sending inbox message: {e}")
            return False

class TaskManager:
    """任务管理器"""

    def __init__(self, bridge: CaoBridge):
        self.bridge = bridge

    async def assign_task(
        self,
        agent_profile: str,
        task: str,
        timeout: int = 3600,
        provider: Optional[str] = None,
        session_name: Optional[str] = None,
    ) -> Dict:
        """分配任务给agent"""
        if not self.bridge.health_check():
            return {"success": False, "error": "CAO service not available. Run 'python3 cao_bridge.py install' to install CAO"}

        # 创建session
        if provider or session_name:
            session_result = self.bridge.create_session_with_provider(
                agent_profile=agent_profile,
                provider=provider,
                session_name=session_name,
            )
        else:
            session_result = self.bridge.create_session(agent_profile)
        if not session_result:
            return {"success": False, "error": "Failed to create session"}

        terminal_id = session_result.get("id")
        if not terminal_id:
            return {"success": False, "error": "No terminal ID in session result"}

        # 发送任务
        if not self.bridge.send_terminal_input(terminal_id, task):
            return {"success": False, "error": "Failed to send task"}

        # 等待任务完成
        start_time = time.time()
        last_output = ""

        while time.time() - start_time < timeout:
            await asyncio.sleep(10)  # 每10秒检查一次

            output = self.bridge.get_terminal_output(terminal_id)
            if output != last_output:
                last_output = output
                print(f"Task progress: {len(output)} chars output...")

            # 检查任务是否完成（简单的启发式检查）
            if self._is_task_complete(output):
                return {
                    "success": True,
                    "terminal_id": terminal_id,
                    "output": output,
                    "execution_time": time.time() - start_time
                }

        # 超时
        return {
            "success": False,
            "error": "Task timeout",
            "terminal_id": terminal_id,
            "partial_output": last_output
        }

    def _is_task_complete(self, output: str) -> bool:
        """启发式检查任务是否完成"""
        # 检查常见的完成标识符
        completion_indicators = [
            "task completed",
            "analysis complete",
            "report generated",
            "finished",
            "done",
            "=== ",
            "#### ",
            "总结"
        ]

        output_lower = output.lower()
        return any(indicator in output_lower for indicator in completion_indicators)

    def monitor_task(self, terminal_id: str) -> None:
        """监控任务执行状态"""
        print(f"Monitoring terminal {terminal_id}...")

        last_length = 0
        while True:
            try:
                terminal = self.bridge.get_terminal(terminal_id)
                if not terminal:
                    print("Terminal not found")
                    break

                output = self.bridge.get_terminal_output(terminal_id)
                current_length = len(output)

                if current_length > last_length:
                    new_content = output[last_length:]
                    print(f"New output ({len(new_content)} chars):")
                    print(new_content[:500])  # 只显示新内容的前500字符
                    if len(new_content) > 500:
                        print("...")
                    print("-" * 50)
                    last_length = current_length

                # 检查是否完成
                if self._is_task_complete(output):
                    print("Task appears to be completed!")
                    break

                time.sleep(30)  # 每30秒检查一次

            except KeyboardInterrupt:
                print("\nMonitoring stopped by user")
                break
            except Exception as e:
                print(f"Monitoring error: {e}")
                time.sleep(60)

def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description="CAO Agent Orchestrator CLI")
    parser.add_argument("--base-url", default=CAO_API_BASE, help="CAO API base URL")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Health check
    health_parser = subparsers.add_parser("health", help="Check CAO service health")

    # Install CAO
    install_parser = subparsers.add_parser("install", help="Install CAO service using uvx")

    # List sessions
    list_parser = subparsers.add_parser("list", help="List sessions")

    # Create session
    create_parser = subparsers.add_parser("create", help="Create new session")
    create_parser.add_argument("agent_profile", choices=["developer", "code-reviewer", "researcher"],
                             help="Agent profile")
    create_parser.add_argument("--session-name", help="Optional session name")
    create_parser.add_argument("--provider", help="Optional provider (e.g. droid, claude_code, codex, q_cli, kiro_cli)")

    # Monitor terminal
    monitor_parser = subparsers.add_parser("monitor", help="Monitor terminal")
    monitor_parser.add_argument("terminal_id", help="Terminal ID to monitor")

    # Get terminal info
    terminal_parser = subparsers.add_parser("terminal", help="Get terminal info")
    terminal_parser.add_argument("terminal_id", help="Terminal ID")

    # Get output
    output_parser = subparsers.add_parser("output", help="Get terminal output")
    output_parser.add_argument("terminal_id", help="Terminal ID")
    output_parser.add_argument("--mode", default="full", help="Output mode (depends on CAO, e.g. full/recent/last)")

    # Delete terminal
    delete_parser = subparsers.add_parser("delete", help="Delete terminal")
    delete_parser.add_argument("terminal_id", help="Terminal ID to delete")

    # Assign task (interactive)
    assign_parser = subparsers.add_parser("assign", help="Assign task to agent")
    assign_parser.add_argument("agent_profile", choices=["developer", "code-reviewer", "researcher"],
                             help="Agent profile")
    assign_parser.add_argument("--timeout", type=int, default=3600, help="Task timeout in seconds")
    assign_parser.add_argument("--file", help="Read task from file")
    assign_parser.add_argument("--provider", help="Optional provider (e.g. droid, claude_code, codex, q_cli, kiro_cli)")
    assign_parser.add_argument("--session-name", help="Optional session name")

    # Inbox messages
    inbox_list_parser = subparsers.add_parser("inbox-list", help="List inbox messages for a terminal")
    inbox_list_parser.add_argument("terminal_id", help="Terminal ID")
    inbox_list_parser.add_argument("--limit", type=int, default=20, help="Max messages")
    inbox_list_parser.add_argument("--status", help="Optional status filter (pending/delivered/failed)")

    inbox_send_parser = subparsers.add_parser("inbox-send", help="Send an inbox message to a terminal")
    inbox_send_parser.add_argument("receiver_id", help="Receiver terminal ID")
    inbox_send_parser.add_argument("sender_id", help="Sender terminal ID")
    inbox_send_parser.add_argument("message", help="Message content")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    bridge = CaoBridge(args.base_url)

    if args.command == "health":
        if bridge.health_check():
            print("✅ CAO service is healthy")
        else:
            print("❌ CAO service is not available")
            print("   Run 'python3 cao_bridge.py install' to install CAO")
            sys.exit(1)

    elif args.command == "install":
        if bridge.install_cao_if_needed():
            print("🎉 CAO service installation completed successfully!")
            print("   Run 'python3 cao_bridge.py health' to verify status")
        else:
            print("❌ CAO service installation failed")
            sys.exit(1)

    elif args.command == "list":
        sessions = bridge.list_sessions()
        if not sessions:
            print("No active sessions")
            return

        print(f"Found {len(sessions)} sessions:")
        for session in sessions:
            print(f"  📋 {session['name']} (ID: {session.get('id', 'N/A')})")
            terminals = bridge.get_session_terminals(session['name'])
            for terminal in terminals:
                print(f"    🔧 Terminal: {terminal['id']} ({terminal.get('agent_profile', 'Unknown')})")

    elif args.command == "create":
        if args.provider:
            session = bridge.create_session_with_provider(args.agent_profile, args.provider, args.session_name)
        else:
            session = bridge.create_session(args.agent_profile, args.session_name)
        if session:
            print(f"✅ Session created successfully")
            print(f"   Session: {session.get('name')}")
            print(f"   Terminal ID: {session.get('id')}")
            print(f"   Agent: {session.get('agent_profile')}")
        else:
            print("❌ Failed to create session")
            sys.exit(1)

    elif args.command == "monitor":
        task_manager = TaskManager(bridge)
        task_manager.monitor_task(args.terminal_id)

    elif args.command == "terminal":
        terminal = bridge.get_terminal(args.terminal_id)
        if terminal:
            print(json.dumps(terminal, ensure_ascii=False, indent=2))
        else:
            print(f"Terminal not found: {args.terminal_id}")
            sys.exit(1)

    elif args.command == "output":
        output = bridge.get_terminal_output(args.terminal_id, args.mode)
        if output:
            print(f"Output from terminal {args.terminal_id}:")
            print("-" * 50)
            print(output)
            print("-" * 50)
            print(f"Total: {len(output)} characters")
        else:
            print(f"No output available for terminal {args.terminal_id}")

    elif args.command == "delete":
        if bridge.delete_terminal(args.terminal_id):
            print(f"✅ Terminal {args.terminal_id} deleted successfully")
        else:
            print(f"❌ Failed to delete terminal {args.terminal_id}")

    elif args.command == "assign":
        # 读取任务内容
        if args.file:
            try:
                with open(args.file, 'r', encoding='utf-8') as f:
                    task_content = f.read()
            except Exception as e:
                print(f"❌ Error reading task file: {e}")
                sys.exit(1)
        else:
            print("Enter task description (Ctrl+D to finish):")
            task_content = sys.stdin.read()

        if not task_content.strip():
            print("❌ Task description cannot be empty")
            sys.exit(1)

        # 分配任务
        async def run_assignment():
            task_manager = TaskManager(bridge)
            result = await task_manager.assign_task(
                args.agent_profile,
                task_content,
                timeout=args.timeout,
                provider=args.provider,
                session_name=args.session_name,
            )

            if result.get("success"):
                print("✅ Task completed successfully!")
                print(f"Terminal ID: {result.get('terminal_id')}")
                print(f"Execution time: {result.get('execution_time', 0):.2f} seconds")
                print(f"Output length: {len(result.get('output', ''))} characters")

                # 保存输出到文件
                output_file = f"task_output_{result.get('terminal_id', 'unknown')}.txt"
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(result.get('output', ''))
                print(f"Output saved to: {output_file}")
            else:
                print(f"❌ Task failed: {result.get('error', 'Unknown error')}")
                if result.get('terminal_id'):
                    print(f"Terminal ID: {result.get('terminal_id')}")
                    partial_output = result.get('partial_output', '')
                    if partial_output:
                        print(f"Partial output: {len(partial_output)} characters")

        asyncio.run(run_assignment())

    elif args.command == "inbox-list":
        messages = bridge.get_inbox_messages(args.terminal_id, limit=args.limit, status=args.status)
        print(json.dumps(messages, ensure_ascii=False, indent=2))

    elif args.command == "inbox-send":
        ok = bridge.send_inbox_message(args.receiver_id, args.sender_id, args.message)
        if ok:
            print("✅ Inbox message sent")
        else:
            print("❌ Failed to send inbox message")
            sys.exit(1)

if __name__ == "__main__":
    main()