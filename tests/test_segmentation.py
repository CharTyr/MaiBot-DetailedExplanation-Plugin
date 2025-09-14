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
    def __init__(self):
        self.log_prefix = "test"

    def get_config(self, key, default=None):
        configs = {
            "detailed_explanation.segment_length": 10,
            "detailed_explanation.min_segments": 1,
            "detailed_explanation.max_segments": 2,
            "segmentation.algorithm": "length",
        }
        return configs.get(key, default)


def test_segment_merge_preserves_newlines():
    action = DummyAction()
    content = "A" * 10 + "B" * 10 + "C" * 10
    segments = action._split_content_into_segments(content)
    assert segments == ["A" * 10, "B" * 10 + "\n\n" + "C" * 10]


class DummyMinSegmentsAction(DetailedExplanationAction):
    def __init__(self):
        self.log_prefix = "test"

    def get_config(self, key, default=None):
        configs = {
            "detailed_explanation.segment_length": 30,
            "detailed_explanation.min_segments": 3,
            "detailed_explanation.max_segments": 3,
            "segmentation.algorithm": "length",
        }
        return configs.get(key, default)


def test_resplit_when_below_min_segments():
    action = DummyMinSegmentsAction()
    content = "A" * 40
    segments = action._split_content_into_segments(content)
    assert segments == ["A" * 13, "A" * 13, "A" * 13 + "\n\n" + "A"]
