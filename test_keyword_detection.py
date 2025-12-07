#!/usr/bin/env python3
"""
简单测试关键词检测功能
"""

# 模拟配置
test_config = {
    "keyword_prompts.enable": True,
    "keyword_prompts.case_sensitive": False,
    "keyword_prompts.match_strategy": "highest",
    "keyword_prompts.rules": [
        {
            "keywords": ["技术", "编程", "代码"],
            "prompt": "技术专家角度",
            "priority": 10
        },
        {
            "keywords": ["历史", "文化"],
            "prompt": "历史文化角度",
            "priority": 8
        },
        {
            "keywords": ["科学", "物理"],
            "prompt": "科学角度",
            "priority": 9
        }
    ]
}

class MockAction:
    """模拟 Action 类"""
    def __init__(self, config):
        self.config = config
        self.log_prefix = "[Test]"
    
    def get_config(self, key, default=None):
        return self.config.get(key, default)
    
    def _detect_keyword_prompt(self, user_text: str) -> str:
        """从 plugin.py 复制的检测方法"""
        try:
            if not self.get_config("keyword_prompts.enable", True):
                return ""
            
            rules = self.get_config("keyword_prompts.rules", [])
            if not rules or not isinstance(rules, list):
                return ""
            
            case_sensitive = self.get_config("keyword_prompts.case_sensitive", False)
            match_strategy = self.get_config("keyword_prompts.match_strategy", "highest")
            
            text_to_match = user_text if case_sensitive else user_text.lower()
            matched_rules = []
            
            for rule in rules:
                if not isinstance(rule, dict):
                    continue
                    
                keywords = rule.get("keywords", [])
                prompt = rule.get("prompt", "")
                priority = rule.get("priority", 0)
                
                if not keywords or not prompt:
                    continue
                
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
                        break
            
            if not matched_rules:
                return ""
            
            if match_strategy == "first":
                return matched_rules[0]["prompt"]
            elif match_strategy == "highest":
                matched_rules.sort(key=lambda x: x["priority"], reverse=True)
                return matched_rules[0]["prompt"]
            elif match_strategy == "merge":
                matched_rules.sort(key=lambda x: x["priority"], reverse=True)
                merged_prompt = " ".join([rule["prompt"] for rule in matched_rules])
                return merged_prompt
            else:
                matched_rules.sort(key=lambda x: x["priority"], reverse=True)
                return matched_rules[0]["prompt"]
                
        except Exception as e:
            print(f"检测出错: {e}")
            return ""

def test_keyword_detection():
    """测试关键词检测功能"""
    action = MockAction(test_config)
    
    # 测试1: 技术关键词（优先级 10）
    result1 = action._detect_keyword_prompt("请详细解释一下Python编程的核心概念")
    print(f"测试1 - 技术关键词: {result1}")
    assert result1 == "技术专家角度", f"期望'技术专家角度'，得到'{result1}'"
    
    # 测试2: 历史关键词（优先级 8）
    result2 = action._detect_keyword_prompt("讲讲中国历史上的重要事件")
    print(f"测试2 - 历史关键词: {result2}")
    assert result2 == "历史文化角度", f"期望'历史文化角度'，得到'{result2}'"
    
    # 测试3: 科学关键词（优先级 9）
    result3 = action._detect_keyword_prompt("物理学中的量子力学原理")
    print(f"测试3 - 科学关键词: {result3}")
    assert result3 == "科学角度", f"期望'科学角度'，得到'{result3}'"
    
    # 测试4: 多关键词匹配，应返回优先级最高的
    result4 = action._detect_keyword_prompt("讲讲编程的历史发展")
    print(f"测试4 - 多关键词: {result4}")
    assert result4 == "技术专家角度", f"期望'技术专家角度'（优先级10），得到'{result4}'"
    
    # 测试5: 无匹配关键词
    result5 = action._detect_keyword_prompt("今天天气怎么样")
    print(f"测试5 - 无匹配: '{result5}'")
    assert result5 == "", f"期望空字符串，得到'{result5}'"
    
    # 测试6: 大小写不敏感
    result6 = action._detect_keyword_prompt("请解释PYTHON编程")
    print(f"测试6 - 大小写: {result6}")
    assert result6 == "技术专家角度", f"期望'技术专家角度'，得到'{result6}'"
    
    print("\n✅ 所有测试通过！")

if __name__ == "__main__":
    test_keyword_detection()
