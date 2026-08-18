from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AssetTests(unittest.TestCase):
    def test_all_five_workflows_are_json_and_contain_no_key(self):
        workflow_dir = ROOT / "workflows"
        workflows = sorted(workflow_dir.glob("*.json"))
        self.assertEqual(len(workflows), 5)
        node_types = set()
        for path in workflows:
            value = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("nodes", value)
            node_types.update(node["type"] for node in value["nodes"])
            self.assertNotIn("YINCHAO_API_KEY", path.read_text(encoding="utf-8"))
            self.assertNotIn("Bearer ", path.read_text(encoding="utf-8"))
        self.assertEqual(
            node_types,
            {
                "YinChaoGenerateLyrics",
                "YinChaoGenerateMusic",
                "YinChaoReferenceMusic",
                "YinChaoExtendMusic",
            },
        )

    def test_nodes_are_v3_only(self):
        source = (ROOT / "yinchao_music" / "nodes.py").read_text(encoding="utf-8")
        root_entrypoint = (ROOT / "__init__.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        self.assertIn("comfy_api.latest", source)
        self.assertIn("comfy_entrypoint", source)
        self.assertIn("comfy_entrypoint", root_entrypoint)
        self.assertNotIn("NODE_CLASS_MAPPINGS", source)
        classes = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
        }
        self.assertTrue(
            {
                "YinChaoGenerateLyrics",
                "YinChaoGenerateMusic",
                "YinChaoReferenceMusic",
                "YinChaoExtendMusic",
            }.issubset(classes)
        )

    def test_registry_metadata_points_to_public_repository(self):
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        publishing = (ROOT / "REGISTRY_PUBLISHING.md").read_text(encoding="utf-8")
        self.assertIn(
            'Repository = "https://github.com/yinhcao/ComfyUI-YinChao"',
            pyproject,
        )
        self.assertIn('PublisherId = "yinhcao"', pyproject)
        self.assertIn("PublisherId", publishing)

    def test_readme_switch_and_license_metadata_are_present(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        english_readme = (ROOT / "README.en.md").read_text(encoding="utf-8")
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("[English](README.en.md)", readme)
        self.assertIn("[中文](README.md)", english_readme)
        self.assertIn("MIT License", license_text)
        self.assertIn('license = { file = "LICENSE" }', pyproject)

    def test_readmes_contain_v4_promotion_and_user_onboarding(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        english_readme = (ROOT / "README.en.md").read_text(encoding="utf-8")
        self.assertIn("音潮音乐大模型 V4.0 重磅上线", readme)
        self.assertIn("¥0.22/首", readme)
        self.assertIn("YinChao Music V4.0 is now live", english_readme)
        self.assertIn("¥0.22 per song", english_readme)
        self.assertNotIn("当前代码托管在", readme)
        self.assertNotIn("source code is hosted", english_readme)

    def test_settings_js_is_present_at_runtime_and_in_python_package(self):
        root_settings = ROOT / "js" / "settings.js"
        package_settings = ROOT / "yinchao_music" / "js" / "settings.js"
        self.assertEqual(
            root_settings.read_text(encoding="utf-8"),
            package_settings.read_text(encoding="utf-8"),
        )
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('yinchao_music = ["js/*.js"]', pyproject)


if __name__ == "__main__":
    unittest.main()
