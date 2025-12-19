import os
import sys
import types

# Ensure project root on path for importing plugin module
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Stub modules required by plugin.py
src = types.ModuleType("src")
src.__path__ = []  # mark as package
sys.modules.setdefault("src", src)

config_pkg = types.ModuleType("src.config")
config_pkg.__path__ = []
sys.modules["src.config"] = config_pkg

config_mod = types.ModuleType("src.config.config")
class _DummyBot:
    nickname = "Mai"
    alias_names = []
    qq_account = "bot"
    platform = "test"
class _DummyPersonality:
    personality = ""
    reply_style = ""
    plan_style = ""
config_mod.global_config = types.SimpleNamespace(bot=_DummyBot(), personality=_DummyPersonality())
sys.modules["src.config.config"] = config_mod

mood_pkg = types.ModuleType("src.mood")
mood_pkg.__path__ = []
sys.modules["src.mood"] = mood_pkg

mood_mod = types.ModuleType("src.mood.mood_manager")
class _DummyMood:
    mood_state = "平静"
class _DummyMoodManager:
    def get_mood_by_chat_id(self, *_args, **_kwargs):
        return _DummyMood()
mood_mod.mood_manager = _DummyMoodManager()
sys.modules["src.mood.mood_manager"] = mood_mod

plugin_system = types.ModuleType("src.plugin_system")
class BaseAction:
    def __init__(self, *args, **kwargs):
        pass
class BasePlugin:  # pragma: no cover - minimal stub
    pass
class BaseCommand:  # pragma: no cover
    pass
class BaseTool:  # pragma: no cover
    def __init__(self, *args, **kwargs):
        self.plugin_config = kwargs.get("plugin_config") if kwargs else None
        self.chat_stream = kwargs.get("chat_stream") if kwargs else None
        self.chat_id = None
class ActionInfo:  # pragma: no cover
    pass
class ActionActivationType:
    LLM_JUDGE = "llm_judge"
    KEYWORD = "keyword"
    ALWAYS = "always"
    RANDOM = "random"
    NEVER = "never"
class ComponentInfo:  # pragma: no cover
    pass
class ConfigField:
    def __init__(self, type, default=None, description=""):
        self.type = type
        self.default = default
        self.description = description
class ToolParamType:  # pragma: no cover
    STRING = "string"

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
plugin_system.BaseCommand = BaseCommand
plugin_system.BaseTool = BaseTool
plugin_system.ActionInfo = ActionInfo
plugin_system.ActionActivationType = ActionActivationType
plugin_system.ComponentInfo = ComponentInfo
plugin_system.ConfigField = ConfigField
plugin_system.ToolParamType = ToolParamType
plugin_system.register_plugin = register_plugin
plugin_system.get_logger = get_logger
sys.modules["src.plugin_system"] = plugin_system

apis = types.ModuleType("src.plugin_system.apis")
class DummyLLMAPI:  # pragma: no cover
    def get_available_models(self):
        return {}
class DummyToolAPI:  # pragma: no cover
    def get_tool_instance(self, *_args, **_kwargs):
        return None
class DummySendAPI:  # pragma: no cover
    async def text_to_stream(self, *args, **kwargs):
        return True
class DummyMessageAPI:  # pragma: no cover
    def get_messages_by_time_in_chat(self, *args, **kwargs):
        return []
apis.llm_api = DummyLLMAPI()
apis.tool_api = DummyToolAPI()
apis.send_api = DummySendAPI()
apis.message_api = DummyMessageAPI()
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
