# 更新日志 (Changelog)

## [1.4.2] - 2025-12-23

### 修复 (Fixed)
- 适配 MaiBot 0.12+：`mood` 模块移除后不再导致插件加载失败（`No module named 'src.mood'`）

### 兼容性 (Compatibility)
- ✅ `main` 分支面向 MaiBot 0.12+（情绪注入自动降级为默认心情文案）
- ✅ 需要 MaiBot 0.11 及更早版本的完整情绪注入请使用 `maibot-0.11` 分支

## [1.4.1] - 2025-12-19

### 新增功能 (Added)
- **会话上下文注入**：新增 `[conversation_context]` 配置节，在长文生成前自动带入“最近对话摘录”，更适合多轮追问/承接上文场景

### 优化 (Improved)
- **性能**：上下文消息查询移至线程执行，避免阻塞事件循环
- **效果**：上下文选取加入去噪/去重、保留最近尾部、相关性挑选与回复链优先

### 兼容性 (Compatibility)
- **联网插件适配**：支持 `google_search_plugin` 的 `web_search` 工具名；保留 `search_online` 回退，并可通过 `content_generation.search_tool_names` 配置优先级

## [1.4.0] - 2025-12-07

### 新增功能 (Added)
- **关键词检测与动态 Prompt 配置**：新增 `[keyword_prompts]` 配置节，支持根据用户输入中的关键词动态选择和加载对应的 prompt 提示词
  - 支持自定义关键词-prompt 映射规则
  - 每个规则可配置关键词列表、自定义 prompt 和优先级
  - 支持三种匹配策略：first（第一个匹配）、highest（优先级最高）、merge（合并所有匹配）
  - 支持大小写敏感/不敏感配置
  - 预置 6 个领域规则：技术、历史文化、科学、商业经济、医学健康、艺术设计

### 实现细节 (Implementation)
- 在 `DetailedExplanationAction` 类中添加 `_detect_keyword_prompt()` 方法
- 在 `DetailedExplanationCommand` 类中添加 `_detect_keyword_prompt()` 方法
- 修改 `_generate_detailed_content()` 方法，集成动态 prompt 选择逻辑
- 更新 `config_schema` 添加 `keyword_prompts` 配置节
- 在配置文件中添加完整的关键词规则示例

### 配置示例 (Configuration)
```toml
[keyword_prompts]
enable = true
case_sensitive = false
match_strategy = "highest"

[[keyword_prompts.rules]]
keywords = ["技术", "编程", "代码", "算法", "开发", "程序"]
prompt = "请以技术专家的角度进行深入的技术解释..."
priority = 10
```

### 兼容性 (Compatibility)
- ✅ 完全向后兼容，不会影响现有功能
- ✅ 保持原有的 LLM 判断和关键词激活机制
- ✅ 保持原有的 persona 保留和 mood 注入功能
- ✅ 默认启用，如不需要可通过 `enable = false` 关闭

### 测试 (Testing)
- ✅ 代码语法检查通过
- ✅ 配置文件 TOML 语法验证通过
- ✅ 关键词检测功能单元测试全部通过（6/6）
  - 技术关键词检测
  - 历史关键词检测
  - 科学关键词检测
  - 多关键词优先级处理
  - 无匹配关键词处理
  - 大小写不敏感处理

### 文档更新 (Documentation)
- 更新 README.md，添加关键词检测功能说明
- 在主要特性部分突出显示新功能
- 在配置说明部分添加详细的配置参数说明
- 提供使用场景示例

---

## [1.3.0] - 之前版本

### 主要特性
- 智能激活与人设风格融合
- 直连 LLM 长文生成
- 使用 replyer 模型集合
- 智能分段发送
- 可选联网搜索增强
- 自动配置迁移

---

**注：本版本由 Snow AI CLI 协助开发**
