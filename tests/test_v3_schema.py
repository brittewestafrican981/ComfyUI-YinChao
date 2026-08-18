from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch


class _InputOutputType:
    class Input:
        def __init__(self, name, **kwargs):
            self.name = name
            self.kwargs = kwargs

    class Output:
        def __init__(self, **kwargs):
            self.kwargs = kwargs


class _Schema:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class _NodeOutput:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class V3SchemaTests(unittest.TestCase):
    def test_all_nodes_build_v3_schema_without_comfy_runtime(self):
        io = types.SimpleNamespace(
            ComfyNode=type("ComfyNode", (), {}),
            Schema=_Schema,
            NodeOutput=_NodeOutput,
            String=_InputOutputType,
            Combo=_InputOutputType,
            Float=_InputOutputType,
            Audio=_InputOutputType,
        )
        comfy_api = types.ModuleType("comfy_api")
        latest = types.ModuleType("comfy_api.latest")
        latest.ComfyExtension = type("ComfyExtension", (), {})
        latest.io = io
        latest.ui = types.SimpleNamespace(PreviewAudio=lambda *args, **kwargs: None)
        comfy_api.latest = latest
        with patch.dict(sys.modules, {"comfy_api": comfy_api, "comfy_api.latest": latest}):
            sys.modules.pop("yinchao_music.nodes", None)
            from yinchao_music import nodes

            node_classes = [
                nodes.YinChaoGenerateLyrics,
                nodes.YinChaoGenerateMusic,
                nodes.YinChaoReferenceMusic,
                nodes.YinChaoExtendMusic,
            ]
            schemas = [node.define_schema() for node in node_classes]

        self.assertEqual(
            [schema.kwargs["node_id"] for schema in schemas],
            [
                "YinChaoGenerateLyrics",
                "YinChaoGenerateMusic",
                "YinChaoReferenceMusic",
                "YinChaoExtendMusic",
            ],
        )
        self.assertTrue(all(schema.kwargs["not_idempotent"] for schema in schemas))


if __name__ == "__main__":
    unittest.main()
