"""ASO MCP Client — 与 aso-mcp (Node.js MCP server) 通信的 Python stdio 客户端.

MCP (Model Context Protocol) stdio 传输协议:
  - 客户端和服务端通过子进程的 stdin/stdout 通信
  - 每条消息是一行 JSON (NDJSON: newline-delimited JSON)
  - 使用 JSON-RPC 2.0 格式

握手流程:
  1. Client → Server: initialize 请求
  2. Server → Client: initialize 响应
  3. Client → Server: notifications/initialized 通知
  4. Client → Server: tools/list 请求
  5. Server → Client: tools/list 响应
  6. Client → Server: tools/call 请求
  7. Server → Client: tools/call 响应

aso-mcp 暴露的工具:
  - aso_evaluate_keywords: 关键词研究 (popularity/difficulty/brand classification)

用法:
  with ASOMcpClient() as client:
      result = client.call_tool("aso_evaluate_keywords", {"keywords": "meditation,sleep"})
      print(result)
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── 常量 ──────────────────────────────────────────────────────

_MCP_PROTOCOL_VERSION = "2024-11-05"
_CLIENT_NAME = "launchforge-aso"
_CLIENT_VERSION = "1.0.0"

_ASO_MCP_COMMAND = "aso-mcp"
_ASO_CLI_COMMAND = "aso"

_DEFAULT_TIMEOUT = 30  # 秒
_INIT_TIMEOUT = 10  # 秒


class ASOMcpError(Exception):
    """ASO MCP 客户端错误."""


class ASOMcpNotInstalledError(ASOMcpError):
    """aso-mcp 未安装."""


class ASOMcpTimeoutError(ASOMcpError):
    """MCP 通信超时."""


class ASOMcpToolError(ASOMcpError):
    """工具调用返回错误."""

    def __init__(self, message: str, error_code: str = "") -> None:
        super().__init__(message)
        self.error_code = error_code


# ── MCP stdio 客户端 ──────────────────────────────────────────

class ASOMcpClient:
    """与 aso-mcp Node.js 进程通信的 MCP stdio 客户端.

    生命周期:
      1. __enter__ / start() — 启动 aso-mcp 子进程并完成 MCP 握手
      2. call_tool() — 调用 MCP 工具
      3. list_tools() — 列出可用工具
      4. __exit__ / close() — 关闭子进程

    线程安全: 单实例不支持并发调用. 多线程请使用锁或创建多个实例.
    """

    def __init__(
        self,
        command: str = _ASO_MCP_COMMAND,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> None:
        self._command = command
        self._cwd = cwd or os.getcwd()
        self._env = env or dict(os.environ)
        self._timeout = timeout
        self._process: Optional[subprocess.Popen] = None
        self._request_id = 0
        self._lock = threading.Lock()
        self._initialized = False

    # ── 上下文管理器 ──

    def __enter__(self) -> "ASOMcpClient":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    # ── 生命周期 ──

    def start(self) -> None:
        """启动 aso-mcp 子进程并完成 MCP 握手."""
        if self._process is not None:
            return

        # 检查 aso-mcp 是否可用
        if not shutil.which(self._command):
            # 尝试 npx
            if shutil.which("npx"):
                self._command = "npx"
                self._npx_args = [_ASO_MCP_COMMAND]
            else:
                raise ASOMcpNotInstalledError(
                    f"'{_ASO_MCP_COMMAND}' 未找到. 请先安装: npm install -g aso-cli"
                )
        else:
            self._npx_args = []

        # 构建启动命令
        if self._command == "npx":
            cmd = ["npx"] + self._npx_args
        else:
            cmd = [self._command]

        logger.info("启动 aso-mcp: %s", " ".join(cmd))

        try:
            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self._cwd,
                env=self._env,
                text=True,
                bufsize=1,  # 行缓冲
            )
        except FileNotFoundError as exc:
            raise ASOMcpNotInstalledError(
                f"无法启动 '{self._command}': {exc}"
            ) from exc

        # 执行 MCP 握手
        self._initialize()

    def close(self) -> None:
        """关闭 aso-mcp 子进程."""
        if self._process is None:
            return

        try:
            if self._process.poll() is None:
                self._process.stdin.close()
                self._process.terminate()
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                    self._process.wait()
        except Exception as exc:
            logger.warning("关闭 aso-mcp 进程时异常: %s", exc)
        finally:
            self._process = None
            self._initialized = False

    # ── MCP 协议 ──

    def _send_request(self, method: str, params: Optional[Dict] = None) -> Dict:
        """发送 JSON-RPC 请求并等待响应."""
        with self._lock:
            self._request_id += 1
            req_id = self._request_id

        message = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
        }
        if params is not None:
            message["params"] = params

        self._write_message(message)
        return self._read_response(req_id)

    def _send_notification(self, method: str, params: Optional[Dict] = None) -> None:
        """发送 JSON-RPC 通知 (不等待响应)."""
        message = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params is not None:
            message["params"] = params

        self._write_message(message)

    def _write_message(self, message: Dict) -> None:
        """向 aso-mcp stdin 写入一行 JSON."""
        if self._process is None or self._process.stdin is None:
            raise ASOMcpError("aso-mcp 进程未启动")

        line = json.dumps(message, ensure_ascii=False) + "\n"
        try:
            self._process.stdin.write(line)
            self._process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise ASOMcpError(f"写入 aso-mcp stdin 失败: {exc}") from exc

    def _read_response(self, expected_id: int) -> Dict:
        """从 aso-mcp stdout 读取 JSON-RPC 响应, 匹配指定 id."""
        if self._process is None or self._process.stdout is None:
            raise ASOMcpError("aso-mcp 进程未启动")

        import select
        import time

        deadline = time.time() + self._timeout

        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise ASOMcpTimeoutError(
                    f"等待 aso-mcp 响应超时 (id={expected_id}, timeout={self._timeout}s)"
                )

            # 在 Windows 上 select 不能用于 pipe, 用线程替代
            line = self._read_line_with_timeout(remaining)
            if line is None:
                raise ASOMcpTimeoutError(
                    f"读取 aso-mcp 响应超时 (id={expected_id})"
                )

            line = line.strip()
            if not line:
                continue

            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                logger.debug("跳过非 JSON 行: %s", line[:100])
                continue

            # 跳过通知 (没有 id 的消息)
            if "id" not in msg:
                logger.debug("跳过通知: %s", msg.get("method", ""))
                continue

            if msg["id"] != expected_id:
                logger.debug("跳过不匹配的响应: id=%s (期望 %s)", msg["id"], expected_id)
                continue

            if "error" in msg:
                err = msg["error"]
                raise ASOMcpToolError(
                    err.get("message", "未知错误"),
                    error_code=err.get("code", ""),
                )

            return msg.get("result", {})

    def _read_line_with_timeout(self, timeout: float) -> Optional[str]:
        """带超时地读取一行 (跨平台兼容)."""
        import queue
        import threading

        result_queue: queue.Queue = queue.Queue()

        def _reader():
            try:
                line = self._process.stdout.readline()
                result_queue.put(line)
            except Exception as exc:
                result_queue.put(exc)

        t = threading.Thread(target=_reader, daemon=True)
        t.start()
        t.join(timeout=timeout)

        if t.is_alive():
            return None

        try:
            result = result_queue.get_nowait()
            if isinstance(result, Exception):
                raise result
            return result
        except queue.Empty:
            return None

    def _initialize(self) -> None:
        """执行 MCP 初始化握手."""
        result = self._send_request(
            "initialize",
            {
                "protocolVersion": _MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {
                    "name": _CLIENT_NAME,
                    "version": _CLIENT_VERSION,
                },
            },
        )

        server_info = result.get("serverInfo", {})
        logger.info(
            "aso-mcp 已连接: %s v%s",
            server_info.get("name", "unknown"),
            server_info.get("version", "unknown"),
        )

        # 发送 initialized 通知
        self._send_notification("notifications/initialized")
        self._initialized = True

    # ── 公共 API ──

    def list_tools(self) -> List[Dict]:
        """列出 aso-mcp 暴露的所有工具."""
        if not self._initialized:
            raise ASOMcpError("MCP 未初始化, 请先调用 start()")

        result = self._send_request("tools/list")
        return result.get("tools", [])

    def call_tool(self, name: str, arguments: Optional[Dict] = None) -> Any:
        """调用 MCP 工具并返回结果.

        Args:
            name: 工具名称 (如 "aso_evaluate_keywords")
            arguments: 工具参数

        Returns:
            工具返回的内容 (通常是 JSON 解析后的 dict)
        """
        if not self._initialized:
            raise ASOMcpError("MCP 未初始化, 请先调用 start()")

        params: Dict[str, Any] = {"name": name}
        if arguments is not None:
            params["arguments"] = arguments

        result = self._send_request("tools/call", params)

        # MCP 工具返回 content 数组, 每项有 type 和 text
        content = result.get("content", [])
        if not content:
            return result

        # 提取文本内容
        texts: List[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                texts.append(item.get("text", ""))

        # 尝试解析为 JSON
        combined = "\n".join(texts)
        if combined:
            try:
                return json.loads(combined)
            except json.JSONDecodeError:
                return combined

        return result

    # ── 状态检查 ──

    @staticmethod
    def is_available() -> bool:
        """检查 aso-mcp 是否已安装."""
        return shutil.which(_ASO_MCP_COMMAND) is not None or shutil.which("npx") is not None

    @staticmethod
    def is_authenticated() -> bool:
        """检查 aso CLI 是否已完成认证.

        aso auth 成功后会在本地保存 cookie/token.
        我们通过 `aso --help` 检查 CLI 是否可用 (不触发认证流程).
        """
        cli = shutil.which(_ASO_CLI_COMMAND)
        if not cli:
            return False
        try:
            result = subprocess.run(
                [cli, "--help"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False


__all__ = [
    "ASOMcpClient",
    "ASOMcpError",
    "ASOMcpNotInstalledError",
    "ASOMcpTimeoutError",
    "ASOMcpToolError",
]
