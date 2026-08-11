"""Prompt Renderer - 提示词渲染器"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from ..models.master_prompt import MasterPrompt, PromptAST, PromptToken


class PromptRenderer:
    """提示词渲染器"""

    def render_ast(self, ast: PromptAST) -> str:
        """将 AST 渲染为文本提示词"""
        content = ", ".join(token.content for token in ast.tokens if token.content.strip())
        return content.strip()

    def render_master_prompt(self, master: MasterPrompt) -> MasterPrompt:
        """渲染完整 Master Prompt"""
        return master

    def save_json(self, master: MasterPrompt, path: str) -> None:
        """保存为 JSON 格式"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(master.to_json())

    def save_markdown(self, master: MasterPrompt, path: str) -> None:
        """保存为 Markdown 格式"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(master.to_markdown())

    def save_text(self, master: MasterPrompt, path: str) -> None:
        """保存为纯文本格式"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(master.to_text())

    def render_all(self, master: MasterPrompt, base_path: str) -> List[str]:
        """渲染所有格式"""
        paths = []

        json_path = f"{base_path}.json"
        self.save_json(master, json_path)
        paths.append(json_path)

        md_path = f"{base_path}.md"
        self.save_markdown(master, md_path)
        paths.append(md_path)

        txt_path = f"{base_path}.txt"
        self.save_text(master, txt_path)
        paths.append(txt_path)

        return paths