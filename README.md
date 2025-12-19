# 麦麦细说插件 (Detailed Explanation Plugin)

当需要对科普、技术、概念等复杂问题做“长文解释”时，本插件直接生成结构化长文，并智能分段发送。新版已绕过默认回复管道（不使用回复器的分割/表达加工），更贴近“专栏式”输出，同时保留麦麦的人设风格与情绪特点。

## 主要特性

- 智能激活与人设风格融合：在 LLM 判断/关键词触发的基础上，自动注入 bot 人设、表达风格与当前心情，使长文保持麦麦的个性与语气。
- **关键词检测与动态 Prompt（新）**：根据用户输入中的关键词（如"技术"、"历史"、"科学"等），自动选择对应领域的专业 prompt，让回答更精准、更专业。
- 直连 LLM 长文生成：绕过 replyer 管道与全局分割器/表达器，使用 `llm_api` 按结构化提示生成完整长文。
- 使用 replyer 模型集合：默认使用 `model_task_config.replyer` 模型集合，支持更长输出（更适合长文），也可在配置中切换。
- 支持会话上下文：自动带入最近对话摘录，更适合“继续展开/承接上文/多轮追问”等场景。
- 智能分段发送：保持段落完整优先，按设定长度和上限分段发送，可选显示进度与逐段 typing 效果。
- 可选联网搜索增强：与 InternetSearchPlugin 协作，在"auto/always/never"模式下拼接搜索摘要，提升准确性与时效性。
- 自动配置迁移：内置 `config_version` 版本化，升级时自动备份、迁移并写回新的配置结构。

## 激活条件

插件会在以下情况下自动激活：

### 关键词触发

当用户消息包含以下关键词时：`详细 / 科普 / 解释 / 说明 / 原理 / 深入 / 具体 / 详细说说` 等。

### 适用场景

- 科普知识问答
- 技术原理解释
- 概念详细说明
- 复杂问题深入分析
- 学术内容阐述

## 使用示例

```
用户：详细解释一下 RAG 的完整工作流程
麦麦：让我详细说明一下...
麦麦：(1/3) 概览：RAG（Retrieval-Augmented Generation）通过“检索+生成”两阶段...
麦麦：(2/3) 工作原理：①检索准备 ②查询扩展 ③召回候选 ④重排 ⑤上下文构建 ⑥生成器解码...
麦麦：(3/3) 常见误区与实践建议：...
```

## 配置说明

### 插件信息 `[plugin]`

- `enabled`：是否启用插件（默认 true）
- `version`：插件版本（自动维护）
- `config_version`：配置文件版本（用于自动迁移）

### 基本设置 `[detailed_explanation]`

- `enable`：是否启用详细解释功能（默认 true）
- `max_total_length`：长文最大字符数（默认 3000，可按需增大，如 6000+）
- `min_total_length`：长文最小字符数（默认 200，短则自动扩写最多两次）
- `segment_length`：每段目标长度（默认 400）
- `min_segments` / `max_segments`：分段下限/上限（默认 1/4）
- `send_delay`：段间发送延迟（默认 1.5s）
- `show_progress`：是否显示进度提示（默认 true）
- `show_start_hint` / `start_hint_message`：是否显示开场提示与其文案

### 触发设置 `[activation]`

- `activation_mode`：`llm_judge | keyword | mixed`（默认 llm_judge）
- `strict_mode`：严格模式，开启后关键词大小写敏感
- `custom_keywords`：自定义关键词列表

### 生成设置 `[content_generation]`

- `model_task`：使用的模型集合（默认 `replyer`，可改为 `utils`/`utils_small`）
- `enable_search`：是否启用联网搜索增强（默认 true）
- `search_mode`：联网触发模式 `auto | always | never`（默认 auto）
- `extra_prompt`：补充到系统结构化提示中的额外指令

### 分段设置 `[segmentation]`

- `algorithm`：`smart | sentence | length`（默认 smart）
- `sentence_separators`：句子分隔符
- `keep_paragraph_integrity`：保持段落完整性（默认 true）
- `min_paragraph_length`：段落合并的最小长度阈值（默认 50）

### 会话上下文 `[conversation_context]`（新增功能）

- `enable`：是否启用会话上下文注入（默认 true）
- `scope`：`chat | user`（默认 chat；群聊推荐 user 以减少噪声）
- `max_messages`：最多带入的历史消息条数（默认 12）
- `time_window_seconds`：时间窗口秒数（默认 1800）
- `max_chars`：上下文最大字符数（默认 1200）
- `per_message_max_chars`：单条历史消息最大字符数（默认 240，超出截断）
- `include_bot_messages`：是否包含机器人历史消息（默认 true）
- `max_intercept_level`：最大拦截等级（默认 0；设为 -1 表示不过滤）

### 关键词检测与动态 Prompt `[keyword_prompts]`（新增功能）

- `enable`：是否启用关键词检测功能（默认 true）
- `case_sensitive`：关键词检测是否大小写敏感（默认 false）
- `match_strategy`：多关键词匹配策略
  - `first`：使用第一个匹配的规则
  - `highest`：使用优先级最高的规则（默认）
  - `merge`：合并所有匹配规则的 prompt
- `rules`：关键词-prompt 映射规则列表，每个规则包含：
  - `keywords`：关键词列表（数组）
  - `prompt`：对应的自定义提示词
  - `priority`：优先级（数字越大优先级越高）

**预置规则示例：**

- 技术类（优先级 10）：检测到"技术"、"编程"、"代码"等关键词，使用技术专家视角
- 历史文化类（优先级 8）：检测到"历史"、"文化"、"传统"等关键词，使用历史文化视角
- 科学类（优先级 9）：检测到"科学"、"物理"、"化学"等关键词，使用科学研究视角
- 商业经济类（优先级 7）：检测到"商业"、"经济"、"市场"等关键词，使用商业分析视角
- 医学健康类（优先级 9）：检测到"医学"、"健康"、"疾病"等关键词，使用医学专业视角
- 艺术设计类（优先级 6）：检测到"艺术"、"设计"、"美学"等关键词，使用艺术审美视角

**使用场景：**

```
用户：详细解释一下 Python 编程的核心概念
→ 检测到关键词"编程"，自动使用"技术专家视角"的 prompt
→ 生成的内容会包含代码示例、最佳实践、技术对比等

用户：讲讲中国历史上的重要事件
→ 检测到关键词"历史"，自动使用"历史文化视角"的 prompt
→ 生成的内容会包含历史脉络、文化背景、史料引用等
```

## 工作原理与行为差异

- 长文生成：直连 `llm_api.generate_with_model`；默认模型集合为 `replyer`，更适合长文输出。
- 分段发送：插件自行分段和发送，不走系统的回复分割器或表达方式加工；首次段落是否“引用回复”由开场提示开关决定。
- 人设与情绪：从 `bot_config.toml` 读取昵称、别名、人设说明、表达风格、情绪特征，并结合当前心情注入提示词，使输出更风格化。
- 联网增强：在 `auto` 模式下遇到时效/知识性问题会触发检索摘要拼接，再生成长文（依赖 InternetSearchPlugin 的 `search_online` 工具）。

## 安装与启用

1. 在 `MaiBot/plugins/detailed_explanation/config.toml` 中设置：
   - `[plugin].enabled = true`
   - `[content_generation].model_task = "replyer"`（默认已设）
   - 如需联网增强，启用 InternetSearchPlugin 并配置其 API Key
2. 重启 MaiBot。

## 配置自动迁移

- 本插件通过 `[plugin].config_version` 与 schema 的默认版本比对，若不一致会自动：备份 → 迁移 → 写回。
- 升级时只需提高代码中的 `config_version` 默认值；旧配置会按新结构生成并迁移原有值。

## 故障排除

- 未激活：检查 `[plugin].enabled` 与触发设置（关键词/模式），查看日志定位。
- 生成失败：检查模型与网络，必要时增大 `generation_timeout`，或暂时关闭 `enable_search`。
- 分段不理想：调整 `segment_length / max_segments / algorithm`，必要时关闭 `keep_paragraph_integrity`。

## 版本信息

- 1.1.0
  - 默认使用 `replyer` 模型集合
  - 绕过 replyer 管道与全局分割/表达器
  - 注入人设/风格/情绪
  - 集成 InternetSearchPlugin（auto/always/never）
  - 启用 `config_version` 自动迁移
- 1.4.1
  - 支持会话上下文注入（多轮追问/承接上文）

## 项目信息

- 许可证：GPL-v3.0-or-later
- 主页/仓库：https://github.com/MaiM-with-u/maibot
- 反馈：请在仓库提交 Issue
