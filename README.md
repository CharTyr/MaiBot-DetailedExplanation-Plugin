# 麦麦细说插件 (Detailed Explanation Plugin)

当需要对科普、技术、概念等复杂问题做“长文解释”时，本插件直接生成结构化长文，并智能分段发送。新版已绕过默认回复管道（不使用回复器的分割/表达加工），更贴近“专栏式”输出，同时保留麦麦的人设风格与情绪特点。

## 主要特性

- 智能激活与人设风格融合：在 LLM 判断/关键词触发的基础上，自动注入 bot 人设、表达风格与当前心情，使长文保持麦麦的个性与语气。
- 直连 LLM 长文生成：绕过 replyer 管道与全局分割器/表达器，使用 `llm_api` 按结构化提示生成完整长文。
- 使用 replyer 模型集合：默认使用 `model_task_config.replyer` 模型集合，支持更长输出（更适合长文），也可在配置中切换。
- 智能分段发送：保持段落完整优先，按设定长度和上限分段发送，可选显示进度与逐段 typing 效果。
- 可选联网搜索增强：与 InternetSearchPlugin 协作，在“auto/always/never”模式下拼接搜索摘要，提升准确性与时效性。
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

## 项目信息

- 许可证：GPL-v3.0-or-later
- 主页/仓库：https://github.com/MaiM-with-u/maibot
- 反馈：请在仓库提交 Issue

