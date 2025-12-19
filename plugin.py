"""
麦麦细说插件 (Detailed Explanation Plugin)

当需要详细解释科普、技术等复杂内容时，生成完整的长文本回复并智能分段发送
"""

import asyncio
import re
import time
from typing import Callable, List, Optional, Tuple, Type

from src.plugin_system import (
    BasePlugin,
    BaseAction,
    BaseCommand,
    BaseTool,
    ActionActivationType,
    ComponentInfo,
    ConfigField,
    ToolParamType,
    register_plugin,
    get_logger,
)
from src.plugin_system.apis import llm_api, message_api, tool_api, send_api
from src.config.config import global_config
from src.mood.mood_manager import mood_manager


logger = get_logger("detailed_explanation")


def _clamp_int(value: object, default: int, *, min_value: int, max_value: int) -> int:
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except Exception:
        return default
    return max(min_value, min(max_value, parsed))


async def _run_sync(func, *args, **kwargs):
    to_thread = getattr(asyncio, "to_thread", None)
    if to_thread:
        return await to_thread(func, *args, **kwargs)
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))


def _extract_tokens(text: str) -> set[str]:
    if not text:
        return set()
    parts = re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]{2,}", text)
    return {p.lower() for p in parts if p}


def _is_low_value_message(text: str) -> bool:
    content = (text or "").strip()
    if not content:
        return True
    if len(content) <= 1:
        return True
    if re.fullmatch(r"[\W_]+", content):
        return True
    if content in {"嗯", "哦", "噢", "啊", "哈", "好", "好的", "行", "可以", "收到", "ok", "OK"}:
        return True
    return False


def _fetch_context_messages(
    *,
    chat_id: str,
    start_time: float,
    end_time: float,
    limit: int,
    include_bot_messages: bool,
    max_intercept_level: Optional[int],
) -> List:
    return message_api.get_messages_by_time_in_chat(
        chat_id=chat_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        limit_mode="latest",
        filter_mai=not include_bot_messages,
        filter_command=True,
        filter_intercept_message_level=max_intercept_level,
    )


def _format_conversation_context_block(
    *,
    messages: List,
    max_messages: int,
    max_chars: int,
    per_message_max_chars: int,
    query_text: str,
    current_user_id: Optional[str],
    scope: str,
    reply_to_message_id: Optional[str],
) -> str:
    if not messages or max_messages <= 0:
        return ""

    bot_id = str(getattr(global_config.bot, "qq_account", "") or "").strip()
    query_tokens = _extract_tokens(query_text)

    cleaned = []
    seen_keys: set[tuple[str, str]] = set()
    for msg in messages:
        speaker = (getattr(msg, "user_nickname", None) or getattr(msg, "user_id", None) or "").strip() or "unknown"
        raw_content = (getattr(msg, "processed_plain_text", None) or getattr(msg, "display_message", None) or "").strip()
        if _is_low_value_message(raw_content):
            continue

        content = re.sub(r"\s+", " ", raw_content)
        if per_message_max_chars > 0 and len(content) > per_message_max_chars:
            content = content[:per_message_max_chars].rstrip() + "…"

        key = (speaker, content)
        if key in seen_keys:
            continue
        seen_keys.add(key)

        cleaned.append(
            {
                "speaker": speaker,
                "content": content,
                "time": float(getattr(msg, "time", 0.0) or 0.0),
                "message_id": str(getattr(msg, "message_id", "") or ""),
                "user_id": str(getattr(msg, "user_id", "") or ""),
            }
        )

    if not cleaned:
        return ""

    if scope == "user" and current_user_id:
        allowed = {str(current_user_id)}
        if bot_id:
            allowed.add(bot_id)
        cleaned = [it for it in cleaned if it["user_id"] in allowed]
        if not cleaned:
            return ""

    baseline_tail = min(4, max_messages)
    tail_items = cleaned[-baseline_tail:] if baseline_tail > 0 else []
    tail_ids = {it["message_id"] for it in tail_items if it["message_id"]}

    start_time = cleaned[0]["time"]
    end_time = cleaned[-1]["time"]
    denom = max(1.0, end_time - start_time)

    for it in cleaned:
        msg_tokens = _extract_tokens(it["content"])
        overlap = len(query_tokens & msg_tokens) if query_tokens else 0
        recency = (it["time"] - start_time) / denom
        score = float(overlap) + 0.25 * recency
        if it["user_id"] and current_user_id and it["user_id"] == str(current_user_id):
            score += 0.5
        if it["user_id"] and bot_id and it["user_id"] == bot_id:
            score += 0.3
        if reply_to_message_id and it["message_id"] == str(reply_to_message_id):
            score += 1000.0
        if it["message_id"] in tail_ids:
            score += 50.0
        it["score"] = score

    selected: List[dict] = []
    selected_ids: set[str] = set()

    for it in cleaned[-baseline_tail:]:
        selected.append(it)
        if it["message_id"]:
            selected_ids.add(it["message_id"])

    remaining_slots = max_messages - len(selected)
    if remaining_slots > 0:
        candidates = [it for it in cleaned[:-baseline_tail] if it["message_id"] not in selected_ids]
        candidates.sort(key=lambda x: x["score"], reverse=True)
        for it in candidates[:remaining_slots]:
            selected.append(it)
            if it["message_id"]:
                selected_ids.add(it["message_id"])

    if reply_to_message_id and str(reply_to_message_id) and str(reply_to_message_id) not in selected_ids:
        for it in cleaned:
            if it["message_id"] == str(reply_to_message_id):
                if selected:
                    selected[0] = it
                else:
                    selected.append(it)
                break

    selected.sort(key=lambda x: x["time"])

    chosen: List[dict] = []
    total_chars = 0
    selected_by_priority = sorted(selected, key=lambda x: x["score"], reverse=True)
    for it in selected_by_priority:
        line = f'{it["speaker"]}: {it["content"]}'
        line_len = len(line) + 1
        if chosen and total_chars + line_len > max_chars:
            continue
        if not chosen and line_len > max_chars:
            line = line[: max_chars - 1] + "…"
            line_len = len(line) + 1
        it["line"] = line
        chosen.append(it)
        total_chars += line_len

    if not chosen:
        return ""

    chosen.sort(key=lambda x: x["time"])
    lines = [it["line"] for it in chosen if it.get("line")]
    if not lines:
        return ""

    return "[会话上下文 - 最近对话摘录]\n" + "\n".join(lines)


async def _build_conversation_context_block(
    *,
    get_config: Callable[[str, object], object],
    chat_id: Optional[str],
    end_time: float,
    exclude_message_id: Optional[str] = None,
    current_user_id: Optional[str] = None,
    reply_to_message_id: Optional[str] = None,
    query_text: str = "",
) -> str:
    if not chat_id:
        return ""

    if not bool(get_config("conversation_context.enable", True)):
        return ""

    scope = str(get_config("conversation_context.scope", "chat")).strip().lower()
    if scope not in {"chat", "user"}:
        scope = "chat"

    max_messages = _clamp_int(get_config("conversation_context.max_messages", 12), 12, min_value=0, max_value=100)
    if max_messages <= 0:
        return ""

    time_window_seconds = _clamp_int(
        get_config("conversation_context.time_window_seconds", 1800), 1800, min_value=0, max_value=86400
    )
    max_chars = _clamp_int(get_config("conversation_context.max_chars", 1200), 1200, min_value=200, max_value=20000)
    per_message_max_chars = _clamp_int(
        get_config("conversation_context.per_message_max_chars", 240), 240, min_value=50, max_value=2000
    )
    include_bot_messages = bool(get_config("conversation_context.include_bot_messages", True))

    max_intercept_level_raw = get_config("conversation_context.max_intercept_level", 0)
    max_intercept_level = None
    try:
        max_intercept_level_int = int(max_intercept_level_raw)  # type: ignore[arg-type]
        if max_intercept_level_int >= 0:
            max_intercept_level = max_intercept_level_int
    except Exception:
        max_intercept_level = 0

    start_time = max(0.0, end_time - float(time_window_seconds)) if time_window_seconds > 0 else 0.0

    try:
        raw_limit = max_messages * 4
        messages = await _run_sync(
            _fetch_context_messages,
            chat_id=chat_id,
            start_time=start_time,
            end_time=end_time,
            limit=raw_limit,
            include_bot_messages=include_bot_messages,
            max_intercept_level=max_intercept_level,
        )
    except Exception as e:
        logger.warning(f"[{chat_id}] 拉取会话上下文失败，已跳过: {e}")
        return ""

    if exclude_message_id:
        messages = [m for m in messages if m.message_id != exclude_message_id]

    if not messages:
        return ""

    return _format_conversation_context_block(
        messages=messages,
        max_messages=max_messages,
        max_chars=max_chars,
        per_message_max_chars=per_message_max_chars,
        query_text=query_text,
        current_user_id=current_user_id,
        scope=scope,
        reply_to_message_id=reply_to_message_id,
    )


class DetailedExplanationAction(BaseAction):
    """详细解释Action - 生成长文本并智能分段发送"""

    # === 基本信息（必须填写）===
    action_name = "detailed_explanation"
    action_description = "生成详细的长文本解释并智能分段发送"
    
    # 改为由 LLM 判断是否需要使用该动作（Planner 会始终看到该动作选项）
    activation_type = ActionActivationType.LLM_JUDGE

    # 备用关键词（用于其他组件或回退策略，不影响 LLM_JUDGE 的主流程）
    _default_activation_keywords = [
        "详细", "科普", "解释", "说明", "原理", "深入", "具体",
        "详细说说", "展开讲讲", "多讲讲", "详细介绍", "深入分析",
        "详细阐述", "深度解析", "请详细", "请展开"
    ]
    activation_keywords = _default_activation_keywords.copy()
    keyword_case_sensitive = False

    # 降低随机激活概率
    random_activation_probability = 0.05

    # === 功能描述（必须填写）===
    action_parameters = {
        "topic": "要详细解释的主题或问题",
        "context": "相关的上下文信息"
    }
    action_require = [
        "仅当用户明确要求详细解释、科普、深入分析时使用",
        "用户使用'详细'、'科普'、'深入'等明确表达求知意图的词汇时使用",
        "涉及复杂科学原理、技术概念、学术问题需要长篇解释时使用",
        "严格避免在日常对话、简单问答、情感交流中使用",
        "如果用户只是随口提到相关词汇而非真正求知，不要使用此功能",
        "优先考虑用户的真实意图，而非单纯的关键词匹配"
    ]
    associated_types = ["text"]

    def __init__(self, *args, **kwargs):
        """初始化并根据配置调整激活方式"""
        super().__init__(*args, **kwargs)

        activation_mode = str(self.get_config("activation.activation_mode", "llm_judge")).lower()
        strict_mode = self.get_config("activation.strict_mode", False)
        custom_keywords = self.get_config("activation.custom_keywords", []) or []

        # 根据配置调整激活方式
        if activation_mode == "keyword":
            keywords = self._default_activation_keywords.copy()
            if isinstance(custom_keywords, list):
                keywords.extend([k for k in custom_keywords if isinstance(k, str)])

            if strict_mode:
                # 严格模式下开启大小写敏感以减少误触发
                self.keyword_case_sensitive = True

            self.activation_keywords = keywords
            self.activation_type = ActionActivationType.KEYWORD
        elif activation_mode == "always":
            self.activation_type = ActionActivationType.ALWAYS
        elif activation_mode == "random":
            self.activation_type = ActionActivationType.RANDOM
        elif activation_mode == "never":
            self.activation_type = ActionActivationType.NEVER
        # 默认保持 LLM_JUDGE

    async def execute(self) -> Tuple[bool, str]:
        """执行详细解释动作"""
        try:
            # 获取配置
            if not self.get_config("detailed_explanation.enable", True):
                logger.info(f"{self.log_prefix} 详细解释功能已禁用")
                return False, "详细解释功能已禁用"

            # 发送开始提示（如果启用）
            if self.get_config("detailed_explanation.show_start_hint", True):
                start_hint = self.get_config("detailed_explanation.start_hint_message", "让我详细说明一下...")
                await self.send_text(start_hint, set_reply=True, reply_message=self.action_message)
                
                # 短暂延迟，让用户看到提示
                await asyncio.sleep(0.5)

            # 生成详细内容
            success, detailed_content = await self._generate_detailed_content()
            if not success or not detailed_content:
                logger.error(f"{self.log_prefix} 生成详细内容失败")
                return False, "生成详细内容失败"

            # 分段并发送
            segments = self._split_content_into_segments(detailed_content)
            await self._send_segments(segments)

            return True, f"成功发送了{len(segments)}段详细解释"

        except Exception as e:
            logger.error(f"{self.log_prefix} 执行详细解释时出错: {e}")
            return False, f"执行详细解释时出错: {str(e)}"

    def _detect_keyword_prompt(self, user_text: str) -> str:
        """
        检测用户输入中的关键词并返回对应的自定义 prompt
        
        Args:
            user_text: 用户输入文本
            
        Returns:
            str: 匹配的自定义 prompt，如果未匹配则返回空字符串
        """
        try:
            # 检查是否启用关键词检测
            if not self.get_config("keyword_prompts.enable", True):
                return ""
            
            # 获取配置
            rules = self.get_config("keyword_prompts.rules", [])
            if not rules or not isinstance(rules, list):
                return ""
            
            case_sensitive = self.get_config("keyword_prompts.case_sensitive", False)
            match_strategy = self.get_config("keyword_prompts.match_strategy", "highest")
            
            # 准备用户文本（根据大小写敏感配置处理）
            text_to_match = user_text if case_sensitive else user_text.lower()
            
            # 收集所有匹配的规则
            matched_rules = []
            
            for rule in rules:
                if not isinstance(rule, dict):
                    continue
                    
                keywords = rule.get("keywords", [])
                prompt = rule.get("prompt", "")
                priority = rule.get("priority", 0)
                
                if not keywords or not prompt:
                    continue
                
                # 检查是否有关键词匹配
                for keyword in keywords:
                    if not isinstance(keyword, str):
                        continue
                    
                    keyword_to_match = keyword if case_sensitive else keyword.lower()
                    
                    if keyword_to_match in text_to_match:
                        matched_rules.append({
                            "prompt": prompt,
                            "priority": priority,
                            "keyword": keyword
                        })
                        logger.info(f"{self.log_prefix} 检测到关键词: {keyword} (优先级: {priority})")
                        break  # 一个规则只需要匹配一次
            
            # 根据策略返回结果
            if not matched_rules:
                return ""
            
            if match_strategy == "first":
                # 返回第一个匹配的
                return matched_rules[0]["prompt"]
            
            elif match_strategy == "highest":
                # 返回优先级最高的
                matched_rules.sort(key=lambda x: x["priority"], reverse=True)
                selected = matched_rules[0]
                logger.info(f"{self.log_prefix} 选择优先级最高的规则 (优先级: {selected['priority']})")
                return selected["prompt"]
            
            elif match_strategy == "merge":
                # 合并所有匹配的 prompt（按优先级排序）
                matched_rules.sort(key=lambda x: x["priority"], reverse=True)
                merged_prompt = " ".join([rule["prompt"] for rule in matched_rules])
                logger.info(f"{self.log_prefix} 合并了 {len(matched_rules)} 个匹配规则")
                return merged_prompt
            
            else:
                # 默认返回优先级最高的
                matched_rules.sort(key=lambda x: x["priority"], reverse=True)
                return matched_rules[0]["prompt"]
                
        except Exception as e:
            logger.warning(f"{self.log_prefix} 关键词检测出错: {e}")
            return ""

    async def _generate_detailed_content(self) -> Tuple[bool, str]:
        """生成详细内容"""
        try:
            # 获取配置
            enable_tools = self.get_config("content_generation.enable_tools", True)
            enable_chinese_typo = self.get_config("content_generation.enable_chinese_typo", False)
            extra_prompt = self.get_config("content_generation.extra_prompt", "")
            model_task_name = self.get_config("content_generation.model_task", "replyer")
            
            # 直连 LLM（绕过 replyer），构造提示词，带入人设与风格
            user_text = self.action_message.processed_plain_text if self.action_message else ""
            topic = str(self.action_data.get("topic", "") or "").strip()
            planner_context = str(self.action_data.get("context", "") or "").strip()
            context_title = "群聊" if (self.chat_stream and self.chat_stream.group_info) else "私聊"
            
            # 检测关键词并获取对应的自定义 prompt
            custom_prompt = self._detect_keyword_prompt(user_text)
            
            # 构建详细解释指令
            if custom_prompt:
                # 如果检测到关键词，使用自定义 prompt
                detailed_instruction = custom_prompt
                logger.info(f"{self.log_prefix} 使用关键词匹配的自定义 prompt")
            else:
                # 否则使用默认的结构化提示
                detailed_instruction = (
                    "请提供详细、完整的解释，不要受到字数限制。"
                    "请按'概览→核心概念→工作原理/流程→关键要点与易错点→案例与对比→局限与常见误区→延伸阅读与参考'的结构展开。"
                    "在每个小节下给出尽可能充足的信息与示例，必要时给出列表与小标题。"
                    "保持回答的逻辑性和条理性，优先中文输出。"
                )
            
            # 追加额外的 prompt 配置（如果有）
            if extra_prompt:
                detailed_instruction += f" {extra_prompt}"

            # 人设与风格
            bot_name = global_config.bot.nickname
            alias = ",也有人叫你" + ",".join(global_config.bot.alias_names) if global_config.bot.alias_names else ""
            identity_block = f"你的名字是{bot_name}{alias}。"
            persona_block = str(global_config.personality.personality or "").strip()
            reply_style = str(global_config.personality.reply_style or "").strip()
            plan_style = str(global_config.personality.plan_style or "").strip()
            try:
                current_mood = mood_manager.get_mood_by_chat_id(self.chat_stream.stream_id).mood_state
            except Exception:
                current_mood = "感觉很平静"

            style_block = (
                f"身份与人设：{identity_block}{persona_block}\n"
                f"表达风格：{reply_style}\n"
                f"行为风格：{plan_style}；当前心情：{current_mood}\n"
            ).strip()

            conversation_context_block = await _build_conversation_context_block(
                get_config=self.get_config,
                chat_id=self.chat_id,
                end_time=float(getattr(self.action_message, "time", time.time()) or time.time()),
                exclude_message_id=str(getattr(self.action_message, "message_id", "") or "") or None,
                current_user_id=str(self.user_id) if self.user_id else None,
                reply_to_message_id=str(getattr(self.action_message, "reply_to", "") or "") or None,
                query_text=(topic or user_text or "").strip(),
            )

            prompt = (
                f"你现在是一个专业的讲解员，负责为用户做深入、系统的科普与解释。\n"
                f"对话场景：{context_title}。\n"
                f"{style_block}\n\n"
            )
            if conversation_context_block:
                prompt += f"{conversation_context_block}\n\n"
            if planner_context:
                prompt += f"[补充上下文]\n{planner_context}\n\n"
            if topic and topic != user_text:
                prompt += f"用户想了解的主题：{topic}\n\n"
            prompt += f"用户消息：{user_text}\n\n请基于用户的真实意图进行回答。{detailed_instruction}"

            models = llm_api.get_available_models()
            task_cfg = models.get(model_task_name) or models.get("replyer")
            if not task_cfg:
                logger.error(f"{self.log_prefix} 未找到可用的模型任务: {model_task_name}")
                return False, ""

            # 可选：联网搜索增强
            search_enabled = bool(self.get_config("content_generation.enable_search", True))
            search_mode = str(self.get_config("content_generation.search_mode", "auto")).lower()
            search_block = ""
            search_query = (topic or user_text or "").strip()
            if search_enabled and search_query:
                need_search = search_mode == "always"
                if search_mode == "auto":
                    # 简单启发式：时效/知识性问题更可能需要联网
                    keywords = [
                        "为什么", "怎么", "如何", "最新", "近期", "新闻", "更新", "发布",
                        "爆料", "评测", "对比", "性能", "配置", "参数",
                    ]
                    need_search = any(k in search_query for k in keywords) or len(search_query) >= 12
                if need_search:
                    try:
                        tool = tool_api.get_tool_instance("search_online")
                        if tool:
                            logger.info(f"{self.log_prefix} 触发联网搜索以增强长文内容")
                            search_res = await tool.direct_execute(question=search_query[:200])  # type: ignore
                            if search_res:
                                search_block = (
                                    "\n\n[联网检索摘要]\n" + str(search_res).strip() +
                                    "\n\n请在保证准确性的前提下吸收以上信息，若与常识冲突以检索为准，避免无依据的臆测与捏造。"
                                )
                    except Exception as e:
                        logger.warning(f"{self.log_prefix} 联网搜索失败，跳过: {e}")

            if search_block:
                prompt = prompt + search_block

            success, content, _, _ = await llm_api.generate_with_model(
                prompt=prompt,
                model_config=task_cfg,
                request_type="detailed_explanation",
            )

            if success and content:
                content = content.strip()

                # 从配置读取最小/最大长度，添加二次扩写逻辑
                min_length = int(self.get_config("detailed_explanation.min_total_length", 200))
                max_length = int(self.get_config("detailed_explanation.max_total_length", 2400))

                # 太短则尝试二次扩写（最多两次）
                retry = 0
                while len(content) < min_length and retry < 2:
                    logger.info(f"{self.log_prefix} 内容偏短({len(content)}<{min_length})，进行第{retry+1}次扩写")
                    expand_prompt = (
                        "在上文基础上继续详细展开，不要重复，补充更多背景、细节、案例与类比，"
                        "并加入‘常见问题与解答’与‘实践建议/操作步骤’两个小节。"
                    )
                    if extra_prompt:
                        expand_prompt += f" {extra_prompt}"
                    succ2, more, _, _ = await llm_api.generate_with_model(
                        prompt=f"基于以下已写内容继续扩写，不要重复：\n\n已写内容：\n{content}\n\n扩写指令：{expand_prompt}",
                        model_config=task_cfg,
                        request_type="detailed_explanation.expand",
                    )
                    if succ2 and more:
                        content = (content + "\n\n" + more.strip()).strip()
                    retry += 1

                # 检查长度上限
                if len(content) > max_length:
                    logger.warning(f"{self.log_prefix} 生成的内容过长({len(content)}字符)，截断到{max_length}字符")
                    content = content[:max_length] + "..."

                logger.info(f"{self.log_prefix} 成功生成详细内容，长度: {len(content)}字符")
                return True, content
            else:
                logger.error(f"{self.log_prefix} 生成详细内容失败")
                return False, ""

        except Exception as e:
            logger.error(f"{self.log_prefix} 生成详细内容时出错: {e}")
            return False, ""

    def _split_content_into_segments(self, content: str) -> List[str]:
        """将内容分割成段落"""
        try:
            # 获取配置
            # 与配置和文档保持一致，默认段长为400字符
            segment_length = self.get_config("detailed_explanation.segment_length", 400)
            min_segments = self.get_config("detailed_explanation.min_segments", 1)
            max_segments = self.get_config("detailed_explanation.max_segments", 4)
            algorithm = self.get_config("segmentation.algorithm", "smart")
            
            # 如果内容较短，不分段
            if len(content) <= segment_length:
                return [content]
            
            segments = []
            
            if algorithm == "smart":
                segments = self._smart_split(content, segment_length, max_segments)
            elif algorithm == "sentence":
                segments = self._sentence_split(content, segment_length, max_segments)
            else:  # length
                segments = self._length_split(content, segment_length, max_segments)
            
            # 确保段数在限制范围内
            if len(segments) < min_segments:
                # 如果段数太少，尝试合并
                return [content]
            elif len(segments) > max_segments:
                # 如果段数太多，合并后面的段，并保留段落间的换行
                tail = "\n\n".join(segments[max_segments-1:])
                segments = segments[:max_segments-1] + [tail]
            
            logger.info(f"{self.log_prefix} 内容分割完成，共{len(segments)}段")
            return segments

        except Exception as e:
            logger.error(f"{self.log_prefix} 分割内容时出错: {e}")
            return [content]  # 出错时返回原内容

    def _prepare_paragraphs(self, content: str) -> List[str]:
        """根据配置处理段落并合并过短段落"""
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', content) if p.strip()]
        keep_integrity = self.get_config("segmentation.keep_paragraph_integrity", True)
        min_length = int(self.get_config("segmentation.min_paragraph_length", 50))

        if not keep_integrity:
            return paragraphs

        merged: List[str] = []
        temp = ""
        for para in paragraphs:
            if temp:
                temp = temp + "\n\n" + para
            else:
                temp = para
            if len(temp) >= min_length:
                merged.append(temp)
                temp = ""

        if temp:
            if merged:
                merged[-1] += "\n\n" + temp
            else:
                merged.append(temp)

        return merged

    def _smart_split(self, content: str, target_length: int, max_segments: int) -> List[str]:
        """智能分割算法"""
        # 处理段落并根据配置合并
        paragraphs = self._prepare_paragraphs(content)
        if not paragraphs:
            return [content]
        
        segments = []
        current_segment = ""
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
                
            # 如果当前段落加上新段落不超过目标长度，合并
            if len(current_segment + paragraph) <= target_length:
                if current_segment:
                    current_segment += "\n\n" + paragraph
                else:
                    current_segment = paragraph
            else:
                # 如果当前段不为空，先保存
                if current_segment:
                    segments.append(current_segment)
                
                # 如果单个段落太长，按句子分割
                if len(paragraph) > target_length:
                    sentences = self._split_by_sentences(paragraph)
                    temp_segment = ""
                    for sentence in sentences:
                        if len(temp_segment + sentence) <= target_length:
                            temp_segment += sentence
                        else:
                            if temp_segment:
                                segments.append(temp_segment)
                            temp_segment = sentence
                    current_segment = temp_segment
                else:
                    current_segment = paragraph
        
        # 添加最后一段
        if current_segment:
            segments.append(current_segment)
        
        return segments

    def _sentence_split(self, content: str, target_length: int, max_segments: int) -> List[str]:
        """按句子分割"""
        keep_integrity = self.get_config("segmentation.keep_paragraph_integrity", True)
        segments: List[str] = []

        if keep_integrity:
            paragraphs = self._prepare_paragraphs(content)
            for paragraph in paragraphs:
                sentences = self._split_by_sentences(paragraph)
                current_segment = ""
                for sentence in sentences:
                    if len(current_segment + sentence) <= target_length:
                        current_segment += sentence
                    else:
                        if current_segment:
                            segments.append(current_segment)
                        current_segment = sentence
                if current_segment:
                    segments.append(current_segment)
        else:
            sentences = self._split_by_sentences(content)
            current_segment = ""
            for sentence in sentences:
                if len(current_segment + sentence) <= target_length:
                    current_segment += sentence
                else:
                    if current_segment:
                        segments.append(current_segment)
                    current_segment = sentence
            if current_segment:
                segments.append(current_segment)

        return segments

    def _length_split(self, content: str, target_length: int, max_segments: int) -> List[str]:
        """按长度分割"""
        keep_integrity = self.get_config("segmentation.keep_paragraph_integrity", True)
        segments: List[str] = []

        if keep_integrity:
            paragraphs = self._prepare_paragraphs(content)
            for paragraph in paragraphs:
                for i in range(0, len(paragraph), target_length):
                    segments.append(paragraph[i:i + target_length])
        else:
            for i in range(0, len(content), target_length):
                segments.append(content[i:i + target_length])

        return segments

    def _split_by_sentences(self, text: str) -> List[str]:
        """按句子分割文本"""
        separators = self.get_config("segmentation.sentence_separators", ["。", "！", "？", ".", "!", "?"])
        
        # 构建正则表达式
        pattern = '([' + ''.join(re.escape(sep) for sep in separators) + '])'
        parts = re.split(pattern, text)
        
        sentences = []
        for i in range(0, len(parts) - 1, 2):
            sentence = parts[i]
            if i + 1 < len(parts):
                sentence += parts[i + 1]  # 加上分隔符
            if sentence.strip():
                sentences.append(sentence)
        
        # 处理最后一部分（如果没有分隔符结尾）
        if len(parts) % 2 == 1 and parts[-1].strip():
            sentences.append(parts[-1])
        
        return sentences

    async def _send_segments(self, segments: List[str]) -> None:
        """分段发送内容"""
        try:
            send_delay = self.get_config("detailed_explanation.send_delay", 1.5)
            show_progress = self.get_config("detailed_explanation.show_progress", True)
            start_hint_enabled = self.get_config("detailed_explanation.show_start_hint", True)
            
            for i, segment in enumerate(segments):
                # 添加进度提示
                if show_progress and len(segments) > 1:
                    segment_with_progress = f"({i+1}/{len(segments)}) {segment}"
                else:
                    segment_with_progress = segment
                
                # 发送段落
                await self.send_text(
                    segment_with_progress,
                    set_reply=(i == 0 and not start_hint_enabled),
                    reply_message=self.action_message if (i == 0 and not start_hint_enabled) else None,
                    typing=(i > 0),
                )
                
                # 如果不是最后一段，等待一段时间
                if i < len(segments) - 1:
                    await asyncio.sleep(send_delay)
                    
            logger.info(f"{self.log_prefix} 成功发送{len(segments)}段内容")

        except Exception as e:
            logger.error(f"{self.log_prefix} 发送段落时出错: {e}")


class DetailedExplanationCommand(BaseCommand):
    """细说命令 - 用户主动触发详细解释"""

    command_name = "detailed_explanation_cmd"
    command_description = "主动触发详细解释功能"
    # 支持: /细说 xxx, /explain xxx, /详细 xxx
    command_pattern = r"^[/／](?:细说|explain|详细|科普)\s*(?P<topic>.*)$"

    async def execute(self) -> Tuple[bool, str, bool]:
        """执行命令"""
        topic = self.matched_groups.get("topic", "").strip()

        if not topic:
            await self.send_text("请告诉我你想了解什么，例如：/细说 量子计算")
            return True, "缺少主题", True

        # 发送开始提示
        show_hint = self.get_config("detailed_explanation.show_start_hint", True)
        if show_hint:
            hint = self.get_config("detailed_explanation.start_hint_message", "让我详细说明一下...")
            await self.send_text(hint)
            await asyncio.sleep(0.5)

        # 生成详细内容
        success, content = await self._generate_content(topic)
        if not success:
            await self.send_text("抱歉，生成详细解释时遇到了问题，请稍后再试")
            return False, "生成失败", True

        # 分段发送
        segments = self._split_content(content)
        await self._send_segments(segments)

        return True, f"成功发送{len(segments)}段解释", True

    def _detect_keyword_prompt(self, user_text: str) -> str:
        """
        检测用户输入中的关键词并返回对应的自定义 prompt
        （与 Action 类中的方法相同）
        
        Args:
            user_text: 用户输入文本
            
        Returns:
            str: 匹配的自定义 prompt，如果未匹配则返回空字符串
        """
        try:
            # 检查是否启用关键词检测
            if not self.get_config("keyword_prompts.enable", True):
                return ""
            
            # 获取配置
            rules = self.get_config("keyword_prompts.rules", [])
            if not rules or not isinstance(rules, list):
                return ""
            
            case_sensitive = self.get_config("keyword_prompts.case_sensitive", False)
            match_strategy = self.get_config("keyword_prompts.match_strategy", "highest")
            
            # 准备用户文本
            text_to_match = user_text if case_sensitive else user_text.lower()
            
            # 收集所有匹配的规则
            matched_rules = []
            
            for rule in rules:
                if not isinstance(rule, dict):
                    continue
                    
                keywords = rule.get("keywords", [])
                prompt = rule.get("prompt", "")
                priority = rule.get("priority", 0)
                
                if not keywords or not prompt:
                    continue
                
                # 检查是否有关键词匹配
                for keyword in keywords:
                    if not isinstance(keyword, str):
                        continue
                    
                    keyword_to_match = keyword if case_sensitive else keyword.lower()
                    
                    if keyword_to_match in text_to_match:
                        matched_rules.append({
                            "prompt": prompt,
                            "priority": priority,
                            "keyword": keyword
                        })
                        logger.info(f"命令检测到关键词: {keyword} (优先级: {priority})")
                        break
            
            # 根据策略返回结果
            if not matched_rules:
                return ""
            
            if match_strategy == "first":
                return matched_rules[0]["prompt"]
            elif match_strategy == "highest":
                matched_rules.sort(key=lambda x: x["priority"], reverse=True)
                logger.info(f"命令选择优先级最高的规则 (优先级: {matched_rules[0]['priority']})")
                return matched_rules[0]["prompt"]
            elif match_strategy == "merge":
                matched_rules.sort(key=lambda x: x["priority"], reverse=True)
                merged_prompt = " ".join([rule["prompt"] for rule in matched_rules])
                logger.info(f"命令合并了 {len(matched_rules)} 个匹配规则")
                return merged_prompt
            else:
                matched_rules.sort(key=lambda x: x["priority"], reverse=True)
                return matched_rules[0]["prompt"]
                
        except Exception as e:
            logger.warning(f"命令关键词检测出错: {e}")
            return ""

    async def _generate_content(self, topic: str) -> Tuple[bool, str]:
        """生成详细内容"""
        try:
            model_task = self.get_config("content_generation.model_task", "replyer")
            extra_prompt = self.get_config("content_generation.extra_prompt", "")

            models = llm_api.get_available_models()
            task_cfg = models.get(model_task) or models.get("replyer")
            if not task_cfg:
                return False, ""
            
            # 检测关键词并获取自定义 prompt
            custom_prompt = self._detect_keyword_prompt(topic)
            
            # 构建详细解释指令
            if custom_prompt:
                # 使用自定义 prompt
                instruction = custom_prompt
                logger.info("命令使用关键词匹配的自定义 prompt")
            else:
                # 使用默认结构化提示
                instruction = "请按'概览→核心概念→工作原理→关键要点→案例说明→常见误区'的结构展开。保持回答的逻辑性和条理性，优先中文输出。"
            
            reply_to_message_id = None
            try:
                if getattr(self.message, "reply", None) and getattr(self.message.reply, "message_info", None):
                    reply_to_message_id = str(getattr(self.message.reply.message_info, "message_id", "") or "") or None
            except Exception:
                reply_to_message_id = None

            conversation_context_block = await _build_conversation_context_block(
                get_config=self.get_config,
                chat_id=getattr(self.message.chat_stream, "stream_id", None),
                end_time=float(getattr(self.message.message_info, "time", time.time()) or time.time()),
                exclude_message_id=str(getattr(self.message.message_info, "message_id", "") or "") or None,
                current_user_id=str(getattr(self.message.message_info.user_info, "user_id", "") or "") or None,
                reply_to_message_id=reply_to_message_id,
                query_text=topic,
            )

            prompt = (
                f"请对以下主题进行详细、系统的解释：\n\n"
                f"主题：{topic}\n\n"
                f"{instruction}"
            )
            if conversation_context_block:
                prompt = f"{conversation_context_block}\n\n" + prompt
            
            if extra_prompt:
                prompt += f" {extra_prompt}"

            # 联网搜索增强
            if self.get_config("content_generation.enable_search", True):
                try:
                    tool = tool_api.get_tool_instance("search_online")
                    if tool:
                        search_res = await tool.direct_execute(question=topic[:200])
                        if search_res:
                            prompt += f"\n\n[参考资料]\n{str(search_res).strip()}"
                except Exception:
                    pass

            success, content, _, _ = await llm_api.generate_with_model(
                prompt=prompt,
                model_config=task_cfg,
                request_type="detailed_explanation.command",
            )

            if success and content:
                max_len = self.get_config("detailed_explanation.max_total_length", 3000)
                if len(content) > max_len:
                    content = content[:max_len] + "..."
                return True, content.strip()
            return False, ""

        except Exception as e:
            logger.error(f"命令生成内容失败: {e}")
            return False, ""

    def _split_content(self, content: str) -> List[str]:
        """分割内容"""
        segment_len = self.get_config("detailed_explanation.segment_length", 400)
        max_segments = self.get_config("detailed_explanation.max_segments", 4)

        if len(content) <= segment_len:
            return [content]

        # 简单按段落分割
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", content) if p.strip()]
        segments = []
        current = ""

        for para in paragraphs:
            if len(current + para) <= segment_len:
                current = (current + "\n\n" + para).strip()
            else:
                if current:
                    segments.append(current)
                current = para

        if current:
            segments.append(current)

        # 限制段数
        if len(segments) > max_segments:
            tail = "\n\n".join(segments[max_segments - 1 :])
            segments = segments[: max_segments - 1] + [tail]

        return segments

    async def _send_segments(self, segments: List[str]) -> None:
        """分段发送"""
        delay = self.get_config("detailed_explanation.send_delay", 1.5)
        show_progress = self.get_config("detailed_explanation.show_progress", True)

        for i, seg in enumerate(segments):
            text = f"({i+1}/{len(segments)}) {seg}" if show_progress and len(segments) > 1 else seg
            await self.send_text(text)
            if i < len(segments) - 1:
                await asyncio.sleep(delay)


class DetailedExplanationTool(BaseTool):
    """详细解释工具 - 供 LLM 调用"""

    name = "detailed_explanation_tool"
    description = "生成详细的长文本解释。当需要对复杂概念、技术原理进行深入解释时使用此工具。"
    parameters = [
        ("topic", ToolParamType.STRING, "要详细解释的主题或问题", True, None),
        ("context", ToolParamType.STRING, "相关的上下文信息（可选）", False, None),
    ]
    available_for_llm = True

    async def execute(self, function_args: dict) -> dict:
        """执行工具"""
        topic = function_args.get("topic", "")
        context = function_args.get("context", "")

        if not topic:
            return {"name": self.name, "content": "请提供要解释的主题"}

        try:
            models = llm_api.get_available_models()
            task_cfg = models.get("replyer")
            if not task_cfg:
                return {"name": self.name, "content": "模型配置不可用"}

            conversation_context_block = await _build_conversation_context_block(
                get_config=self.get_config,
                chat_id=self.chat_id,
                end_time=time.time(),
                query_text=str(topic or "").strip(),
            )

            prompt = f"请对以下主题进行详细解释：\n\n主题：{topic}"
            if conversation_context_block:
                prompt = f"{conversation_context_block}\n\n" + prompt
            if context:
                prompt += f"\n\n[补充上下文]\n{context}"
            prompt += "\n\n请提供结构化、详细的解释。"

            success, content, _, _ = await llm_api.generate_with_model(
                prompt=prompt,
                model_config=task_cfg,
                request_type="detailed_explanation.tool",
            )

            if success and content:
                return {"name": self.name, "content": content.strip()}
            return {"name": self.name, "content": "生成解释失败"}

        except Exception as e:
            logger.error(f"工具执行失败: {e}")
            return {"name": self.name, "content": f"执行出错: {str(e)}"}


@register_plugin
class DetailedExplanationPlugin(BasePlugin):
    """麦麦细说插件主类"""

    # 插件基本信息
    plugin_name: str = "detailed_explanation"
    enable_plugin: bool = True
    dependencies: list[str] = []
    python_dependencies: list[str] = []
    config_file_name: str = "config.toml"

    # 配置节描述
    config_section_descriptions = {
        "plugin": "插件基本信息",
        "detailed_explanation": "详细解释功能配置",
        "activation": "激活方式配置",
        "content_generation": "内容生成配置",
        "segmentation": "分段算法配置",
        "keyword_prompts": "关键词检测与动态Prompt配置",
        "conversation_context": "会话上下文配置",
    }

    # 配置Schema定义
    config_schema: dict = {
        "plugin": {
            "name": ConfigField(type=str, default="detailed_explanation", description="插件名称"),
            "version": ConfigField(type=str, default="1.4.1", description="插件版本"),
            "config_version": ConfigField(type=str, default="1.4.0", description="配置文件版本"),
            "enabled": ConfigField(type=bool, default=True, description="是否启用插件"),
        },
        "detailed_explanation": {
            "enable": ConfigField(type=bool, default=True, description="是否启用详细解释功能"),
            "max_total_length": ConfigField(type=int, default=3000, description="最大总文本长度限制"),
            "min_total_length": ConfigField(type=int, default=200, description="最小总文本长度限制"),
            "segment_length": ConfigField(type=int, default=400, description="每段目标长度"),
            "min_segments": ConfigField(type=int, default=1, description="最小分段数"),
            "max_segments": ConfigField(type=int, default=4, description="最大分段数"),
            "send_delay": ConfigField(type=float, default=1.5, description="分段间发送延迟"),
            "show_progress": ConfigField(type=bool, default=True, description="是否显示进度提示"),
            "show_start_hint": ConfigField(type=bool, default=True, description="是否显示开始提示"),
            "start_hint_message": ConfigField(type=str, default="让我详细说明一下...", description="开始提示消息"),
            "activation_probability": ConfigField(type=float, default=0.1, description="激活概率"),
        },
        "activation": {
            "activation_mode": ConfigField(type=str, default="llm_judge", description="激活类型: llm_judge/keyword/always/random/never"),
            "strict_mode": ConfigField(type=bool, default=False, description="是否启用严格模式"),
            "custom_keywords": ConfigField(type=list, default=[], description="自定义关键词列表"),
        },
        "content_generation": {
            "enable_tools": ConfigField(type=bool, default=True, description="是否启用工具调用"),
            "enable_chinese_typo": ConfigField(type=bool, default=False, description="是否启用中文错别字生成器"),
            "generation_timeout": ConfigField(type=int, default=30, description="生成超时时间"),
            "extra_prompt": ConfigField(type=str, default="", description="额外的prompt指令"),
            "model_task": ConfigField(type=str, default="replyer", description="使用的模型任务集合(如 replyer/utils/utils_small)"),
            "enable_search": ConfigField(type=bool, default=True, description="是否启用联网搜索增强"),
            "search_mode": ConfigField(type=str, default="auto", description="联网搜索触发模式: auto/always/never"),
        },
        "segmentation": {
            "algorithm": ConfigField(type=str, default="smart", description="分段算法类型"),
            "sentence_separators": ConfigField(type=list, default=["。", "！", "？", ".", "!", "?"], description="句子分割符"),
            "keep_paragraph_integrity": ConfigField(type=bool, default=True, description="是否保持段落完整性"),
            "min_paragraph_length": ConfigField(type=int, default=50, description="最小段落长度"),
        },
        "keyword_prompts": {
            "enable": ConfigField(type=bool, default=True, description="是否启用关键词检测功能"),
            "case_sensitive": ConfigField(type=bool, default=False, description="关键词检测是否大小写敏感"),
            "match_strategy": ConfigField(type=str, default="highest", description="多匹配策略: first/highest/merge"),
            "rules": ConfigField(type=list, default=[], description="关键词-prompt映射规则列表"),
        },
        "conversation_context": {
            "enable": ConfigField(type=bool, default=True, description="是否启用会话上下文注入"),
            "scope": ConfigField(type=str, default="chat", description="上下文范围: chat(整个会话)/user(仅当前用户+机器人)"),
            "max_messages": ConfigField(type=int, default=12, description="最多带入的历史消息条数"),
            "time_window_seconds": ConfigField(type=int, default=1800, description="上下文时间窗口(秒)"),
            "max_chars": ConfigField(type=int, default=1200, description="上下文最大字符数(近似)"),
            "per_message_max_chars": ConfigField(type=int, default=240, description="单条历史消息最大字符数(超出截断)"),
            "include_bot_messages": ConfigField(type=bool, default=True, description="是否包含机器人历史消息"),
            "max_intercept_level": ConfigField(
                type=int, default=0, description="最大拦截等级(<=保留)，-1表示不过滤(包含被拦截的消息)"
            ),
        },
    }

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        """获取插件包含的组件列表"""
        return [
            (DetailedExplanationAction.get_action_info(), DetailedExplanationAction),
            (DetailedExplanationCommand.get_command_info(), DetailedExplanationCommand),
            (DetailedExplanationTool.get_tool_info(), DetailedExplanationTool),
        ]
