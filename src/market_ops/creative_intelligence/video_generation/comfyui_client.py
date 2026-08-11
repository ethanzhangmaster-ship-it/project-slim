"""ComfyUI Client - ComfyUI API 客户端

连接本地 ComfyUI，支持：
- 提交 workflow
- 查询任务状态
- 获取生成结果
- 下载视频文件
"""
from __future__ import annotations

import os
import time
import requests
from typing import Any

from .models import GenerationStatus


class ComfyUIClient:
    """ComfyUI API 客户端"""

    def __init__(
        self,
        host: str = "192.168.124.13",
        port: int = 8188,
        timeout: int = 600,
    ):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.base_url = f"http://{host}:{port}"
        os.environ["NO_PROXY"] = host

    def health_check(self) -> dict[str, Any]:
        """检查 ComfyUI 是否可用"""
        try:
            r = requests.get(f"{self.base_url}/system_stats", timeout=10)
            data = r.json()
            devices = data.get("devices", [])
            return {
                "ok": True,
                "version": data.get("system", {}).get("comfyui_version", ""),
                "devices": [
                    {"name": d.get("name", ""), "vram_free_mb": d.get("vram_free", 0) // (1024 * 1024)}
                    for d in devices
                ],
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def submit(self, workflow_json: dict[str, Any]) -> dict[str, Any]:
        """提交 workflow 到 ComfyUI

        Returns:
            {"prompt_id": str, "number": int}
        """
        url = f"{self.base_url}/prompt"
        r = requests.post(url, json={"prompt": workflow_json}, timeout=30)
        r.raise_for_status()
        return r.json()

    def get_status(self, prompt_id: str) -> dict[str, Any]:
        """获取任务状态

        Returns:
            {"status": "running" | "completed" | "not_found", ...}
        """
        # 先查 history
        history_url = f"{self.base_url}/history/{prompt_id}"
        r = requests.get(history_url, timeout=10)
        data = r.json()
        if data and prompt_id in data:
            return {"status": "completed", "data": data[prompt_id]}

        # 再查 queue
        queue_url = f"{self.base_url}/queue"
        r = requests.get(queue_url, timeout=10)
        q = r.json()
        for item in q.get("queue_running", []):
            if isinstance(item, list) and len(item) >= 2 and item[1] == prompt_id:
                return {"status": "running"}
        for item in q.get("queue_pending", []):
            if isinstance(item, list) and len(item) >= 2 and item[1] == prompt_id:
                return {"status": "pending"}

        return {"status": "not_found"}

    def wait_for_completion(
        self,
        prompt_id: str,
        poll_interval: int = 10,
        max_wait: int = 600,
    ) -> dict[str, Any]:
        """轮询等待任务完成

        Returns:
            {"completed": bool, "data": {...} | None, "error": str}
        """
        waited = 0
        while waited < max_wait:
            status = self.get_status(prompt_id)
            if status["status"] == "completed":
                return {"completed": True, "data": status["data"], "error": ""}
            if status["status"] == "not_found":
                return {"completed": False, "data": None, "error": "Task not found"}

            time.sleep(poll_interval)
            waited += poll_interval

        return {"completed": False, "data": None, "error": f"Timeout after {max_wait}s"}

    def get_output_filename(self, prompt_data: dict[str, Any]) -> str:
        """从 completed task 数据中提取输出文件名"""
        outputs = prompt_data.get("outputs", {})
        for node_id, node_out in outputs.items():
            if "gifs" in node_out:
                for g in node_out["gifs"]:
                    return g.get("filename", "")
            if "images" in node_out:
                for img in node_out["images"]:
                    return img.get("filename", "")
        return ""

    def download_file(
        self,
        filename: str,
        output_path: str,
        file_type: str = "output",
    ) -> str:
        """从 ComfyUI 下载文件

        Returns:
            本地文件路径
        """
        url = f"{self.base_url}/view?filename={filename}&type={file_type}"
        r = requests.get(url, timeout=60)
        r.raise_for_status()

        with open(output_path, "wb") as f:
            f.write(r.content)

        return output_path

    def upload_image(self, image_path: str) -> dict[str, Any]:
        """上传图片到 ComfyUI input 目录"""
        url = f"{self.base_url}/upload/image"
        with open(image_path, "rb") as f:
            files = {"image": (os.path.basename(image_path), f, "image/png")}
            data = {"type": "input", "overwrite": "true"}
            r = requests.post(url, files=files, data=data, timeout=30)
        return r.json()

    def generate(
        self,
        workflow_json: dict[str, Any],
        timeout: int = 600,
    ) -> dict[str, Any]:
        """一键生成：提交 + 等待 + 获取结果

        Returns:
            {"success": bool, "prompt_id": str, "filename": str, "error": str}
        """
        # 提交
        submit_result = self.submit(workflow_json)
        prompt_id = submit_result.get("prompt_id", "")
        if not prompt_id:
            return {"success": False, "prompt_id": "", "filename": "", "error": "Submit failed"}

        # 等待
        wait_result = self.wait_for_completion(prompt_id, max_wait=timeout)
        if not wait_result["completed"]:
            return {"success": False, "prompt_id": prompt_id, "filename": "", "error": wait_result["error"]}

        # 获取文件名
        filename = self.get_output_filename(wait_result["data"])
        return {"success": True, "prompt_id": prompt_id, "filename": filename, "error": ""}
