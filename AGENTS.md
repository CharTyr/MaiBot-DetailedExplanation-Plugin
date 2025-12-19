# AGENTS.md - MaiBot Detailed Explanation Plugin

## Project Name

**麦麦细说插件 (MaiBot Detailed Explanation Plugin)**

Intelligent plugin for generating structured long-form explanations with smart segmentation and delivery.

## Overview

The Detailed Explanation Plugin is a sophisticated component for MaiBot that intelligently detects when users need detailed explanations of complex topics (scientific concepts, technical principles, academic content) and generates well-structured, long-form responses. Unlike standard replies, this plugin bypasses the default reply pipeline to maintain consistent persona and style, generates comprehensive content through direct LLM calls, and intelligently segments the output for optimal readability.

This plugin is designed to handle knowledge-intensive questions that benefit from detailed exposition, providing structured explanations with multiple viewpoints, examples, and edge cases. It seamlessly integrates with MaiBot's ecosystem including mood management, persona configuration, and optional internet search enhancement.

The plugin uses a flexible activation system supporting LLM judgment, keyword matching, or manual command triggers, and provides configurable content generation with optional web search integration for improved accuracy on time-sensitive or factual questions.

## Technology Stack

- **Language/Runtime**: Python 3.7+ (async-first)
- **Framework**: MaiBot Plugin System (custom framework)
- **Key Dependencies**:
  - `asyncio` - Asynchronous programming support
  - `re` - Regular expression processing for text segmentation
  - `src.plugin_system` - MaiBot plugin base classes and decorators
  - `src.plugin_system.apis` - LLM, tool, and send APIs
  - `src.config.config` - Global configuration management
  - `src.mood.mood_manager` - Bot emotion/mood state
- **Build/Configuration**: TOML-based configuration with automatic migration
- **Testing**: pytest-compatible unit tests with module stubs
- **Architecture Pattern**: Multi-component plugin with Action, Command, and Tool implementations

## Project Structure

```
MaiBot-DetailedExplanation-Plugin/
├── plugin.py                  # Main plugin implementation (720 lines)
│   ├── DetailedExplanationAction    # Auto-triggered action component
│   ├── DetailedExplanationCommand   # Manual command /细说 xxx
│   ├── DetailedExplanationTool      # LLM-callable tool interface
│   └── DetailedExplanationPlugin    # Main plugin class with schema
├── config.toml               # Configuration file with TOML schema
├── _manifest.json            # Plugin manifest for MaiBot integration
├── README.md                 # Chinese documentation with usage examples
├── LICENSE                   # GPL-v3.0-or-later license
├── tests/
│   └── test_segmentation.py  # Unit tests for segmentation algorithms
└── .gitignore               # Git ignore patterns

**Key Modules:**

- `DetailedExplanationAction`: Monitors chat for keywords/LLM signals indicating need for detailed explanation, orchestrates content generation and segmentation
- `DetailedExplanationCommand`: Handles explicit user commands like `/细说 量子计算` for on-demand detailed explanations
- `DetailedExplanationTool`: Provides LLM with callable interface for generating detailed content during reasoning
- `DetailedExplanationPlugin`: Main plugin class managing configuration schema, auto-migration, component registration
```

## Key Features

- **Intelligent Activation**: Dual-mode detection using LLM judgment (default) or keyword matching; 50+ activation keywords in Chinese; configurable strict mode for case sensitivity
- **Persona Preservation**: Injects bot identity, alias names, personality traits, expression style, behavior patterns, and current mood into generated content
- **Direct LLM Integration**: Bypasses the standard reply pipeline (replyer processor) for unfiltered long-form output; uses configurable model task (default: `replyer` for extended output)
- **Smart Content Generation**: Structured prompt with predefined format (Overview → Core Concepts → Mechanism → Key Points → Examples → Common Misconceptions → Extensions); automatic expansion when content too short; configurable length limits
- **Intelligent Segmentation**: Three algorithms (smart/sentence/length) with paragraph integrity preservation; prevents orphaning short segments; configurable min/max segment limits
- **Staged Sending**: Sends segments with configurable delays; optional progress indicators `(1/3)` format; optional typing effect; fully async non-blocking
- **Internet Search Enhancement**: Optional integration with InternetSearchPlugin; three modes (auto/always/never); heuristic triggers for time-sensitive/knowledge questions
- **Multi-Activation Paths**:
  - Auto-detection via LLM judgment during conversation planning
  - Keyword matching for fallback/explicit triggering
  - Manual command interface `/细说 xxx`, `/explain xxx`, `/详细 xxx`, `/科普 xxx`
  - LLM-callable tool for reasoning-based invocation
- **Flexible Configuration**: TOML-based schema with 20+ parameters; automatic config version migration preserving legacy settings; inline documentation for each parameter
- **Comprehensive Testing**: Unit tests for three segmentation algorithms with edge cases (paragraph merging, short content, overflow)

## Getting Started

### Prerequisites

- MaiBot v0.11.0 or later
- Python 3.7+
- Async-capable Python runtime
- (Optional) InternetSearchPlugin for web search enhancement

### Installation

```bash
# 1. Navigate to MaiBot plugins directory
cd /path/to/MaiBot/plugins/

# 2. Clone or copy plugin
git clone https://github.com/CharTyr/MaiBot-DetailedExplanation-Plugin.git detailed_explanation

# 3. Enable in MaiBot's main configuration
# Add to plugins list in MaiBot config.toml:
# plugins = ["detailed_explanation", ...]

# 4. (Optional) Enable InternetSearchPlugin for search enhancement
# InternetSearchPlugin must be installed and configured with API keys

# 5. Restart MaiBot
# The plugin will auto-initialize configuration on first load
```

### Usage

**Automatic Activation (Default):**
```
User: 详细解释一下 RAG 的完整工作流程
Bot: 让我详细说明一下...
Bot: (1/3) 概览：RAG（Retrieval-Augmented Generation）是一种...
Bot: (2/3) 工作原理：...
Bot: (3/3) 常见问题与解答：...
```

**Manual Command:**
```
User: /细说 量子计算
Bot: 让我详细说明一下...
Bot: (1/2) 量子计算基础概念...
Bot: (2/2) 应用与前景...
```

**Alternative Commands:**
- `/explain TOPIC` - English style command
- `/详细 TOPIC` - Explicit detail request
- `/科普 TOPIC` - Educational explanation

## Development

### Available Scripts

The plugin doesn't include npm/build scripts (pure Python). Testing uses pytest:

```bash
# Run segmentation algorithm tests
cd tests/
pytest test_segmentation.py -v

# Run specific test
pytest test_segmentation.py::test_paragraph_merging_smart -v
```

### Development Workflow

1. **Modify Core Logic**: Edit `plugin.py` directly (DetailedExplanationAction, Command, Tool classes)
2. **Update Configuration**: Modify `config.toml` and bump `config_version` in schema if changing structure
3. **Add Tests**: Create test cases in `tests/test_segmentation.py` following existing patterns
4. **Update Manifest**: If adding new features, update `_manifest.json` components list
5. **Test Locally**: Use provided test suite; mock MaiBot APIs as shown in `test_segmentation.py`
6. **Documentation**: Update `README.md` (Chinese) or this AGENTS.md file (English)

**Key Development Notes:**
- The plugin uses `ActionActivationType.LLM_JUDGE` by default - changing this affects all instances
- Segmentation algorithms are performance-critical; use existing test patterns when modifying
- Configuration auto-migration occurs automatically; the schema version comparison triggers backup/migrate/writeback cycle
- Content generation uses `llm_api.generate_with_model()` with `request_type` parameter for tracking/quota

### Testing Strategy

```python
# Tests use mock stubs for MaiBot dependencies
# Each test instantiates a DummyAction with custom config
# Segmentation algorithms tested with edge cases:

def test_paragraph_merging_smart():
    """Verify short paragraphs merge while preserving structure"""
    action = _build_action("smart")
    content = "A" * 3 + "\n\n" + "B" * 3 + "\n\n" + "C" * 20
    segments = action._split_content_into_segments(content)
    assert segments == ["A" * 3 + "\n\n" + "B" * 3, "C" * 20]
```

## Configuration

All configuration lives in `config.toml` with the following sections:

### `[plugin]` - Plugin Metadata
```toml
name = "detailed_explanation"      # Unique identifier
version = "1.3.0"                   # Plugin version
config_version = "1.2.0"            # Schema version (triggers migration)
enabled = true                      # Enable/disable plugin entirely
```

### `[detailed_explanation]` - Core Behavior
```toml
enable = true                       # Feature enable flag
max_total_length = 3000             # Max chars before truncation
min_total_length = 200              # Min chars before triggering expansion
segment_length = 400                # Target characters per segment
min_segments = 1                    # Minimum segment count
max_segments = 4                    # Maximum segment count (merges excess)
send_delay = 1.5                    # Seconds between segment sends
show_progress = true                # Show (1/3) progress indicator
show_start_hint = true              # Show "让我详细说明一下..." prefix
start_hint_message = "..."          # Custom opening message
```

### `[activation]` - Trigger Configuration
```toml
activation_mode = "llm_judge"       # Activation type: llm_judge|keyword|always|random|never
strict_mode = false                 # Keyword case sensitivity
custom_keywords = []                # Additional trigger words beyond defaults
```

**Default Keywords (50+):** `详细`, `科普`, `解释`, `说明`, `原理`, `深入`, `具体`, `详细说说`, `展开讲讲`, `多讲讲`, `详细介绍`, `深入分析`, `详细阐述`, `深度解析`, `请详细`, `请展开`

### `[content_generation]` - LLM & Generation
```toml
enable_tools = true                 # Enable tool calls in LLM
enable_chinese_typo = false         # Add realistic typos (personality)
generation_timeout = 30             # Seconds before timeout
extra_prompt = ""                   # Additional generation instructions
model_task = "replyer"              # Model set: replyer|utils|utils_small
enable_search = true                # Enable internet search integration
search_mode = "auto"                # Search trigger: auto|always|never
```

### `[segmentation]` - Algorithm Configuration
```toml
algorithm = "smart"                 # Split strategy: smart|sentence|length
sentence_separators = [...]         # Sentence ending markers (. ! ? etc)
keep_paragraph_integrity = true     # Merge short paragraphs
min_paragraph_length = 50           # Minimum chars before considering for merge
```

## Architecture

### High-Level Flow

```
User Message
    ↓
[Activation Detection]
    ├─→ LLM judges if needs detailed explanation (default)
    ├─→ Keyword matcher triggers (fallback)
    └─→ Manual command `/细说` (explicit)
    ↓
[Content Generation]
    ├─→ Inject persona (name, aliases, style, mood)
    ├─→ Query LLM with structured prompt
    ├─→ (Optional) Augment with internet search
    ├─→ Check length: if short → expand; if long → truncate
    └─→ Return structured content
    ↓
[Smart Segmentation]
    ├─→ Select algorithm (smart/sentence/length)
    ├─→ Preserve paragraph boundaries if configured
    ├─→ Enforce min/max segment limits
    └─→ Return segment list
    ↓
[Async Delivery]
    ├─→ Send opening hint (optional)
    ├─→ For each segment:
    │   ├─→ Add progress indicator (optional)
    │   ├─→ Send with typing effect (if not first)
    │   └─→ Wait send_delay seconds before next
    └─→ Complete
```

### Component Interactions

- **DetailedExplanationAction**: Monitors all incoming messages; triggered by LLM judgment or keywords
- **DetailedExplanationCommand**: Explicitly invoked via regex pattern matching in message text
- **DetailedExplanationTool**: Made available to LLM during reasoning; allows agent to request detailed explanations as needed
- **Global Dependencies**:
  - `llm_api` for content generation
  - `tool_api` for accessing search_online tool
  - `send_api` for message transmission
  - `global_config` for bot identity (name, personality)
  - `mood_manager` for current emotional state

### Configuration Auto-Migration

When plugin starts:
1. Compare loaded `config_version` with schema default version
2. If mismatch:
   - Backup current config
   - Load schema defaults
   - Migrate existing values to new structure
   - Write back merged config
   - Log migration details

This ensures backward compatibility across versions.

## Contributing

Contributions welcome! Please:

1. Follow existing code style (PEP 8 with async considerations)
2. Add tests for new features (use test_segmentation.py as template)
3. Update README.md (Chinese) and AGENTS.md (English) 
4. Ensure config backward compatibility (use config_version migration)
5. Test with actual MaiBot if possible

## License

**GPL-v3.0-or-later**

Copyright © 2025 CharTyr

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

See LICENSE file for full text.

## Project Information

- **Author**: CharTyr
- **Repository**: https://github.com/CharTyr/MaiBot-DetailedExplanation-Plugin
- **Homepage**: https://github.com/CharTyr/MaiBot-DetailedExplanation-Plugin
- **MaiBot Compatibility**: v0.11.0+
- **Current Version**: 1.4.1

---

## Implementation Details for Developers

### Segmentation Algorithms

The plugin provides three segmentation strategies with different characteristics:

**1. Smart Algorithm** (default, recommended)
- Processes paragraphs (separated by `\n\n`)
- Merges short paragraphs respecting `min_paragraph_length`
- For long paragraphs, further splits by sentences
- Best for mixed-length content

**2. Sentence Algorithm**
- Splits by sentence delimiters (configurable, default: 。！？.!?)
- Respects paragraph boundaries if enabled
- Good for narrative content with clear sentence structure

**3. Length Algorithm**
- Simple character-count based splitting
- No semantic awareness
- Fastest but may break mid-word for edge cases

### Activation Modes

- `llm_judge` (default): LLM evaluates conversation context to decide activation
- `keyword`: Simple case-insensitive substring matching against keyword list
- `always`: Triggers on every message (testing only)
- `random`: Probabilistic activation (testing only)
- `never`: Disabled (for debugging)

### Search Integration

When `enable_search = true`:
- `search_mode = "auto"`: Heuristically detects time-sensitive/knowledge questions
- `search_mode = "always"`: Always queries internet before generation
- `search_mode = "never"`: Disables search completely

Heuristic keywords: `为什么`, `怎么`, `如何`, `最新`, `近期`, `新闻`, `更新`, `发布`, `爆料`, `评测`, `对比`, `性能`, `配置`, `参数`

---

**Generated**: December 8, 2025
**Analysis Tool**: Snow AI CLI
**Document Version**: 1.0
