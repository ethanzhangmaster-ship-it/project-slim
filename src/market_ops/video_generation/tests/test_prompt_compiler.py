"""Prompt Compiler Tests"""
import sys
import unittest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.market_ops.video_generation.compiler.prompt_compiler import BlueprintParser, PromptCompiler
from src.market_ops.video_generation.compiler.prompt_optimizer import PromptOptimizer
from src.market_ops.video_generation.compiler.prompt_statistics import PromptStatisticsGenerator
from src.market_ops.video_generation.models.master_prompt import (
    CompilerContext,
    MasterPrompt,
    PromptAST,
    PromptToken,
)


class TestBlueprintParser(unittest.TestCase):
    """测试 Blueprint 解析器"""

    def test_parse_empty_dir(self):
        """测试解析空目录"""
        parser = BlueprintParser()
        ctx = parser.parse("/nonexistent/path")
        self.assertIsInstance(ctx, CompilerContext)
        self.assertEqual(len(ctx.shot_lists), 0)

    def test_parse_context_fields(self):
        """测试解析上下文字段"""
        parser = BlueprintParser()
        ctx = parser.parse("/nonexistent/path")
        self.assertTrue(hasattr(ctx, "camera_specs"))
        self.assertTrue(hasattr(ctx, "shot_lists"))
        self.assertTrue(hasattr(ctx, "asset_specs"))
        self.assertTrue(hasattr(ctx, "editing_specs"))
        self.assertTrue(hasattr(ctx, "subtitle_specs"))
        self.assertTrue(hasattr(ctx, "music_specs"))
        self.assertTrue(hasattr(ctx, "prompt_packages"))


class TestPromptOptimizer(unittest.TestCase):
    """测试提示词优化器"""

    def test_deduplicate(self):
        """测试去重"""
        optimizer = PromptOptimizer()
        tokens = [
            PromptToken(content="beautiful", type="scene", weight=1.0),
            PromptToken(content="beautiful", type="scene", weight=0.8),
        ]
        ast = PromptAST(tokens=tokens)
        optimized = optimizer.optimize(ast)
        self.assertEqual(len(optimized.tokens), 1)

    def test_merge_similar(self):
        """测试相似词合并"""
        optimizer = PromptOptimizer()
        tokens = [
            PromptToken(content="cinematic", type="scene", weight=1.0),
            PromptToken(content="movie", type="scene", weight=1.0),
        ]
        ast = PromptAST(tokens=tokens)
        optimized = optimizer.optimize(ast)
        self.assertTrue(any("cinematic film look" in t.content for t in optimized.tokens))

    def test_sort(self):
        """测试排序"""
        optimizer = PromptOptimizer()
        tokens = [
            PromptToken(content="fx", type="fx", weight=1.0),
            PromptToken(content="scene", type="scene", weight=1.0),
            PromptToken(content="camera", type="camera", weight=1.0),
        ]
        ast = PromptAST(tokens=tokens)
        optimized = optimizer.optimize(ast)
        types = [t.type for t in optimized.tokens]
        order = ["scene", "camera", "fx"]
        self.assertEqual(types, order)


class TestPromptCompiler(unittest.TestCase):
    """测试提示词编译器"""

    def test_compile_structure(self):
        """测试编译结构"""
        compiler = PromptCompiler("/nonexistent/path")
        master = compiler.compile()
        self.assertIsInstance(master, MasterPrompt)
        self.assertIsInstance(master.scenes, list)

    def test_compile_and_save(self):
        """测试编译并保存"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            compiler = PromptCompiler("/nonexistent/path")
            result = compiler.compile_and_save(tmpdir)
            self.assertIn("master_prompt", result)
            self.assertIn("validation", result)
            self.assertIn("statistics", result)
            self.assertIn("output_files", result)


class TestPromptStatistics(unittest.TestCase):
    """测试提示词统计"""

    def test_generate_statistics(self):
        """测试生成统计"""
        stats_gen = PromptStatisticsGenerator()
        master = MasterPrompt(variant_id="V001")
        stats = stats_gen.generate(master)
        self.assertEqual(stats.total_tokens, 0)
        self.assertEqual(stats.total_prompts, 0)


if __name__ == "__main__":
    import sys
    unittest.main()