"""
麦麦细说插件 (Detailed Explanation Plugin)

当需要详细解释科普、技术等复杂内容时，生成完整的长文本回复并智能分段发送
"""

import asyncio
import re
from typing import List, Tuple, Type, Union

from src.plugin_system import (
    BasePlugin,
    BaseAction,
    ActionInfo,
    ActionActivationType,
    ComponentInfo,
    ConfigField,
    register_plugin,
    get_logger,
)
from src.plugin_system.apis import generator_api, send_api


logger = get_logger("detailed_explanation")


class DetailedExplanationAction(BaseAction):
    """详细解释Action - 生成长文本并智能分段发送"""

    # === 基本信息（必须填写）===
    action_name = "detailed_explanation"
    action_description = "生成详细的长文本解释并智能分段发送"
    
    # 改为由 LLM 判断是否需要使用该动作（Planner 会始终看到该动作选项）
    activation_type = ActionActivationType.LLM_JUDGE

    # 备用关键词（用于其他组件或回退策略，不影响 LLM_JUDGE 的主流程）
    activation_keywords = [
        "详细", "科普", "解释", "说明", "原理", "深入", "具体",
        "详细说说", "展开讲讲", "多讲讲", "详细介绍", "深入分析",
        "详细阐述", "深度解析", "请详细", "请展开"
    ]
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

    async def _generate_detailed_content(self) -> Tuple[bool, str]:
        """生成详细内容"""
        try:
            # 获取配置
            enable_tools = self.get_config("content_generation.enable_tools", True)
            enable_chinese_typo = self.get_config("content_generation.enable_chinese_typo", False)
            extra_prompt = self.get_config("content_generation.extra_prompt", "")
            
            # 构建额外信息，指导生成详细内容（结构化，促进长文输出）
            detailed_instruction = (
                "请提供详细、完整的解释，不要受到字数限制。"
                "请按‘概览→核心概念→工作原理/流程→关键要点与易错点→案例与对比→局限与常见误区→延伸阅读与参考’的结构展开。"
                "在每个小节下给出尽可能充足的信息与示例，必要时给出列表与小标题。"
                "保持回答的逻辑性和条理性，优先中文输出。"
            )
            
            if extra_prompt:
                detailed_instruction += f" {extra_prompt}"

            # 调用生成API，禁用分割器以获得完整长文本
            success, llm_response = await generator_api.generate_reply(
                chat_stream=self.chat_stream,
                reply_message=self.action_message,
                extra_info=detailed_instruction,
                reply_reason="用户需要详细解释",
                enable_tool=enable_tools,
                enable_splitter=False,  # 关键：禁用分割器
                enable_chinese_typo=enable_chinese_typo,
                request_type="detailed_explanation",
                from_plugin=True,
            )

            if success and llm_response and llm_response.content:
                content = llm_response.content.strip()

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
                    succ2, resp2 = await generator_api.generate_reply(
                        chat_stream=self.chat_stream,
                        reply_message=self.action_message,
                        extra_info=expand_prompt,
                        reply_reason="长文二次扩写",
                        enable_tool=enable_tools,
                        enable_splitter=False,
                        enable_chinese_typo=enable_chinese_typo,
                        request_type="detailed_explanation",
                        from_plugin=True,
                    )
                    if succ2 and resp2 and resp2.content:
                        content = (content + "\n\n" + resp2.content.strip()).strip()
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
                # 如果段数太多，合并后面的段
                segments = segments[:max_segments-1] + ["".join(segments[max_segments-1:])]
            
            logger.info(f"{self.log_prefix} 内容分割完成，共{len(segments)}段")
            return segments

        except Exception as e:
            logger.error(f"{self.log_prefix} 分割内容时出错: {e}")
            return [content]  # 出错时返回原内容

    def _smart_split(self, content: str, target_length: int, max_segments: int) -> List[str]:
        """智能分割算法"""
        # 首先按段落分割
        paragraphs = re.split(r'\n\s*\n', content)
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
        sentences = self._split_by_sentences(content)
        segments = []
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
        segments = []
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
            
            for i, segment in enumerate(segments):
                # 添加进度提示
                if show_progress and len(segments) > 1:
                    segment_with_progress = f"({i+1}/{len(segments)}) {segment}"
                else:
                    segment_with_progress = segment
                
                # 发送段落
                await self.send_text(segment_with_progress)
                
                # 如果不是最后一段，等待一段时间
                if i < len(segments) - 1:
                    await asyncio.sleep(send_delay)
                    
            logger.info(f"{self.log_prefix} 成功发送{len(segments)}段内容")

        except Exception as e:
            logger.error(f"{self.log_prefix} 发送段落时出错: {e}")


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
        "content_generation": "内容生成配置",
        "segmentation": "分段算法配置"
    }

    # 配置Schema定义
    config_schema: dict = {
        "plugin": {
            "name": ConfigField(type=str, default="detailed_explanation", description="插件名称"),
            "version": ConfigField(type=str, default="1.0.0", description="插件版本"),
            "enabled": ConfigField(type=bool, default=True, description="是否启用插件"),
        },
        "detailed_explanation": {
            "enable": ConfigField(type=bool, default=True, description="是否启用详细解释功能"),
            "max_total_length": ConfigField(type=int, default=3000, description="最大总文本长度限制"),
            "segment_length": ConfigField(type=int, default=400, description="每段目标长度"),
            "min_segments": ConfigField(type=int, default=1, description="最小分段数"),
            "max_segments": ConfigField(type=int, default=4, description="最大分段数"),
            "send_delay": ConfigField(type=float, default=1.5, description="分段间发送延迟"),
            "show_progress": ConfigField(type=bool, default=True, description="是否显示进度提示"),
            "show_start_hint": ConfigField(type=bool, default=True, description="是否显示开始提示"),
            "start_hint_message": ConfigField(type=str, default="让我详细说明一下...", description="开始提示消息"),
            "activation_probability": ConfigField(type=float, default=0.1, description="激活概率"),
        },
        "content_generation": {
            "enable_tools": ConfigField(type=bool, default=True, description="是否启用工具调用"),
            "enable_chinese_typo": ConfigField(type=bool, default=False, description="是否启用中文错别字生成器"),
            "generation_timeout": ConfigField(type=int, default=30, description="生成超时时间"),
            "extra_prompt": ConfigField(type=str, default="", description="额外的prompt指令"),
        },
        "segmentation": {
            "algorithm": ConfigField(type=str, default="smart", description="分段算法类型"),
            "sentence_separators": ConfigField(type=list, default=["。", "！", "？", ".", "!", "?"], description="句子分割符"),
            "keep_paragraph_integrity": ConfigField(type=bool, default=True, description="是否保持段落完整性"),
            "min_paragraph_length": ConfigField(type=int, default=50, description="最小段落长度"),
        },
    }

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        """获取插件包含的组件列表"""
        return [
            (DetailedExplanationAction.get_action_info(), DetailedExplanationAction),
        ]
