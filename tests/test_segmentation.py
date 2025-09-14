import os
import sys
import types

# Ensure project root on path for importing plugin module
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Stub modules required by plugin.py
src = types.ModuleType("src")
sys.modules.setdefault("src", src)

plugin_system = types.ModuleType("src.plugin_system")
class BaseAction:
    def __init__(self, *args, **kwargs):
        pass
class BasePlugin:  # pragma: no cover - minimal stub
    pass
class ActionInfo:  # pragma: no cover
    pass
class ActionActivationType:
    LLM_JUDGE = "llm_judge"
class ComponentInfo:  # pragma: no cover
    pass
class ConfigField:
    def __init__(self, type, default=None, description=""):
        self.type = type
        self.default = default
        self.description = description

def register_plugin(cls):
    return cls

def get_logger(name):  # pragma: no cover - simple logger stub
    class Logger:
        def info(self, *args, **kwargs):
            pass
        def warning(self, *args, **kwargs):
            pass
        def error(self, *args, **kwargs):
            pass
    return Logger()

plugin_system.BaseAction = BaseAction
plugin_system.BasePlugin = BasePlugin
plugin_system.ActionInfo = ActionInfo
plugin_system.ActionActivationType = ActionActivationType
plugin_system.ComponentInfo = ComponentInfo
plugin_system.ConfigField = ConfigField
plugin_system.register_plugin = register_plugin
plugin_system.get_logger = get_logger
sys.modules["src.plugin_system"] = plugin_system

apis = types.ModuleType("src.plugin_system.apis")
class DummyGeneratorAPI:
    async def generate_reply(self, *args, **kwargs):
        return False, None
apis.generator_api = DummyGeneratorAPI()
apis.send_api = None
sys.modules["src.plugin_system.apis"] = apis

from plugin import DetailedExplanationAction


class DummyAction(DetailedExplanationAction):
    def __init__(self, config=None):
        self.log_prefix = "test"
        if config is None:
            config = {
                "detailed_explanation.segment_length": 10,
                "detailed_explanation.min_segments": 1,
                "detailed_explanation.max_segments": 2,
                "segmentation.algorithm": "length",
            }
        self._config = config

    def get_config(self, key, default=None):
        return self._config.get(key, default)


def test_segment_merge_preserves_newlines():
    action = DummyAction()
    content = "A" * 10 + "B" * 10 + "C" * 10
    segments = action._split_content_into_segments(content)
    assert segments == ["A" * 10, "B" * 10 + "\n\n" + "C" * 10]


def _build_action(algorithm):
    config = {
        "detailed_explanation.segment_length": 25,
        "detailed_explanation.min_segments": 1,
        "detailed_explanation.max_segments": 10,
        "segmentation.algorithm": algorithm,
        "segmentation.keep_paragraph_integrity": True,
        "segmentation.min_paragraph_length": 5,
    }
    return DummyAction(config)


def test_paragraph_merging_smart():
    action = _build_action("smart")
    content = "A" * 3 + "\n\n" + "B" * 3 + "\n\n" + "C" * 20
    segments = action._split_content_into_segments(content)
    assert segments == ["A" * 3 + "\n\n" + "B" * 3, "C" * 20]


def test_paragraph_merging_sentence():
    action = _build_action("sentence")
    content = "A" * 3 + "\n\n" + "B" * 3 + "\n\n" + "C" * 20
    segments = action._split_content_into_segments(content)
    assert segments == ["A" * 3 + "\n\n" + "B" * 3, "C" * 20]


def test_paragraph_merging_length():
    action = _build_action("length")
    content = "A" * 3 + "\n\n" + "B" * 3 + "\n\n" + "C" * 20
    segments = action._split_content_into_segments(content)
    assert segments == ["A" * 3 + "\n\n" + "B" * 3, "C" * 20]
