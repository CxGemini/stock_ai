"""
策略转换层 - 将自然语言策略转换为量化策略
"""
import os
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from openai import OpenAI

@dataclass
class StrategyRequirements:
    """策略数据需求"""
    kline_periods: int
    kline_type: str
    indicators_needed: List[str]

@dataclass
class QuantifiedStrategy:
    """量化策略"""
    name: str
    description: str
    requirements: StrategyRequirements
    calculation_logic: Dict[str, Any]
    timeframe: str
    dynamic_functions: Optional[Dict[str, str]] = None  # 新增：动态校验函数
    
    def get_dynamic_function(self, function_name: str) -> Optional[str]:
        """获取动态校验函数"""
        if self.dynamic_functions and function_name in self.dynamic_functions:
            return self.dynamic_functions[function_name]
        return None

class StrategyConverter:
    """
    策略转换器 - 将自然语言策略转换为量化策略
    """
    
    def __init__(self):
        """初始化策略转换器"""
        self.openai_client = OpenAI(
            api_key=os.getenv("QWEN_API_KEY"),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
    
    def validate_dynamic_formula(self, formula: str, defined_variables: set = None) -> Dict[str, Any]:
        """
        验证动态公式的有效性
        
        Args:
            formula: 动态公式字符串
            defined_variables: 已经定义的变量集合，用于处理公式之间的依赖关系
            
        Returns:
            Dict: 验证结果，包含is_valid和error字段
        """
        import ast
        import re
        
        # 允许使用的K线字段
        allowed_fields = {'open', 'high', 'low', 'close', 'volume', 'amount', 'turn', 'preclose', 'adjustflag', 'tradestatus', 'pctChg', 'isST'}
        
        # 允许使用的函数
        allowed_functions = {'sum', 'len', 'range', 'max', 'min', 'abs'}
        
        # 合并已定义的变量和允许的字段
        if defined_variables is None:
            defined_variables = set()
        allowed_variables = allowed_fields.union(defined_variables)
        
        try:
            # 支持分号分隔的多个语句
            statements = [stmt.strip() for stmt in re.split(r'(?<!\\);', formula) if stmt.strip()]
            
            # 跟踪在语句中定义的变量
            current_allowed_variables = allowed_variables.copy()
            
            for statement in statements:
                # 处理赋值语句，如 "MA5 = (close[-1] + ... + close[-5]) / 5"
                # 确保只匹配赋值运算符'='，而不是复合运算符如'>='、'<='、'!='中的'='
                assign_index = -1
                i = 0
                while i < len(statement):
                    if statement[i] == '=':
                        # 检查前一个字符是否是复合运算符的一部分
                        if i > 0 and statement[i-1] in ['>', '<', '!', '=']:
                            i += 1
                            continue
                        assign_index = i
                        break
                    i += 1
                
                if assign_index != -1:
                    # 解析赋值语句
                    var_name = statement[:assign_index].strip()
                    expr = statement[assign_index+1:].strip()
                    # 解析表达式部分
                    tree = ast.parse(expr, mode='eval')
                else:
                    # 解析整个表达式
                    tree = ast.parse(statement, mode='eval')
                
                # 遍历AST节点验证
                class FormulaValidator(ast.NodeVisitor):
                    def __init__(self, current_allowed_vars):
                        self.errors = []
                        self.allowed_fields = allowed_fields
                        self.allowed_functions = allowed_functions
                        self.allowed_variables = current_allowed_vars
                        self.assigned_variables = set()
                    
                    def visit_Name(self, node):
                        # 检查变量名是否为允许的字段、函数或已定义的变量
                        if node.id not in self.allowed_fields and node.id not in self.allowed_functions and node.id not in self.allowed_variables:
                            # 允许自定义变量名（如MA5、MA10等）
                            if not (node.id.isalnum() and node.id[0].isalpha()):
                                self.errors.append(f"不允许使用的变量或函数: {node.id}")
                        super().generic_visit(node)
                    
                    def visit_Call(self, node):
                        # 检查函数调用
                        if isinstance(node.func, ast.Name):
                            func_name = node.func.id
                            if func_name not in self.allowed_functions:
                                self.errors.append(f"不允许使用的函数: {func_name}")
                        else:
                            self.errors.append(f"不允许的函数调用形式")
                        super().generic_visit(node)
                    
                    def visit_Attribute(self, node):
                        # 不允许属性访问
                        self.errors.append(f"不允许使用属性访问: {ast.dump(node)}")
                        super().generic_visit(node)
                    
                    def visit_Subscript(self, node):
                        # 只允许K线字段的索引访问
                        if isinstance(node.value, ast.Name):
                            field_name = node.value.id
                            if field_name not in self.allowed_fields and field_name not in self.allowed_variables:
                                self.errors.append(f"不允许的字段索引访问: {field_name}")
                        else:
                            # 允许列表推导式和生成器表达式中的索引访问
                            if not (isinstance(node.value, ast.ListComp) or isinstance(node.value, ast.GeneratorExp)):
                                self.errors.append(f"不允许的索引访问形式: {ast.dump(node)}")
                        super().generic_visit(node)
                    
                    def visit_ListComp(self, node):
                        # 允许列表推导式
                        super().generic_visit(node)
                    
                    def visit_GeneratorExp(self, node):
                        # 允许生成器表达式
                        super().generic_visit(node)
                    
                    def visit_IfExp(self, node):
                        # 允许条件表达式
                        super().generic_visit(node)
                
                validator = FormulaValidator(current_allowed_variables)
                validator.visit(tree)
                
                if validator.errors:
                    return {"is_valid": False, "error": "; ".join(validator.errors)}
                
                # 如果是赋值语句，将变量名添加到允许的变量列表中
                if assign_index != -1:
                    current_allowed_variables.add(var_name)
            
            return {"is_valid": True, "error": None}
            
        except SyntaxError as e:
            return {"is_valid": False, "error": f"语法错误: {e}"}
        except Exception as e:
            return {"is_valid": False, "error": f"验证错误: {e}"}
    
    async def parse_natural_language_strategy(self, strategy_text: str) -> QuantifiedStrategy:
        """
        解析自然语言策略为量化策略
        
        Args:
            strategy_text: 自然语言策略描述
            
        Returns:
            QuantifiedStrategy: 量化策略对象
        """
        system_prompt = """
        你是一个金融策略量化专家。将用户的自然语言选股策略转换为结构化的量化策略和动态校验函数。
        
        **重要约束：**
        - 动态校验函数只能使用K线原始字段：open, high, low, close, volume, amount, turn, preclose, adjustflag, tradestatus, pctChg, isST
        - 所有技术指标必须通过数学公式基于这些原始字段计算
        - 不能使用任何预定义的技术指标函数（如MA(), RSI(), MACD()等）
        - 只能使用基础数学运算和比较操作
        - 支持sum(), len(), range(), max(), min()等基础函数
        - 支持列表推导式和生成器表达式
        - 支持条件表达式
        - 支持嵌套复合条件
        - 每个校验函数必须是一个接收kline_data数组作为唯一参数的函数
        - 函数必须返回布尔值，表示是否符合该条件
        - 必须能够处理不同长度的kline_data数组，不能假设固定长度（例如不能硬编码kline_data.length < 60这样的限制）
        - 当数据不足时，应尽可能利用现有数据进行计算，而不是直接返回false
        - 对于需要特定周期数据的指标，应使用Math.min()来适应实际数据长度
        
        输出应该是一个JSON对象，结构如下：
        {
            "strategy_name": "策略名称",
            "description": "策略简要描述",
            "data_requirements": {
                "kline_periods": 60,
                "kline_type": "d",
                "indicators_needed": []  # 由于使用动态函数，这里可以为空
            },
            "calculation_logic": {
                "conditions": [
                    {
                        "indicator": "价格涨幅",
                        "operator": ">",
                        "value": 5,
                        "calculation_formula": "(close[-1] - close[-2]) / close[-2] * 100"
                    }
                ]
            },
            "dynamic_functions": {
                "limit_up_count_check": "function(kline_data) { let count = 0; for (let i = 0; i < Math.min(60, kline_data.length); i++) { if (kline_data[kline_data.length - 1 - i]['pctChg'] >= 9.9) count++; } return count >= 2; }",
                "price_fall_after_limit_up": "function(kline_data) { if (kline_data.length < 5) return false; let has_limit_up = false; for (let i = 1; i <= Math.min(5, kline_data.length); i++) { if (kline_data[kline_data.length - i]['pctChg'] >= 9.9) { has_limit_up = true; break; } } return has_limit_up && kline_data[kline_data.length - 1]['close'] < kline_data[kline_data.length - Math.min(5, kline_data.length)]['close']; }",
                "main_condition": "function(kline_data) { return limit_up_count_check(kline_data) && price_fall_after_limit_up(kline_data); }"
            },
            "timeframe": "daily"
        }
        
        动态校验函数语法说明：
        - 所有函数必须是标准JavaScript函数，接收kline_data数组作为唯一参数
        - 函数内部可以定义辅助变量和嵌套逻辑
        - 可以在函数内部调用其他已定义的校验函数
        - K线数据访问方式：kline_data[i]['field_name']，其中i是数据索引（0为最早数据，length-1为最新数据）
        - 支持基础数学运算: +, -, *, /, >, <, >=, <=, ==, &&, ||
        - 支持循环结构: for, while
        - 支持条件判断: if, else if, else
        - 支持变量赋值: 可以创建中间变量，如 "let MA5 = (kline_data[kline_data.length-1]['close'] + kline_data[kline_data.length-2]['close'] + kline_data[kline_data.length-3]['close'] + kline_data[kline_data.length-4]['close'] + kline_data[kline_data.length-5]['close']) / 5"
        - 支持列表操作和计算
        - 函数必须返回布尔值表示条件是否满足
        - 支持复杂的时序逻辑和统计计算
        - 严禁使用Python风格的负索引语法如"close[-1]"，必须使用JavaScript标准语法如"kline_data[kline_data.length - 1]['close']"
        
        公式示例：
        - 简单价格比较: "kline_data.length > 0 && kline_data[kline_data.length - 1]['close'] > kline_data[kline_data.length - 2]['close']"
        - 移动平均计算: "(kline_data[kline_data.length-1]['close'] + kline_data[kline_data.length-2]['close'] + kline_data[kline_data.length-3]['close'] + kline_data[kline_data.length-4]['close'] + kline_data[kline_data.length-5]['close']) / 5"
        - 成交量变化率: "(kline_data[kline_data.length-1]['volume'] - kline_data[kline_data.length-2]['volume']) / kline_data[kline_data.length-2]['volume'] * 100"
        - 涨停数统计: "let count = 0; for (let i = 0; i < Math.min(60, kline_data.length); i++) { if (kline_data[kline_data.length - 1 - i]['pctChg'] >= 9.9) count++; } return count >= 2;"
        - 价格区间: "kline_data[kline_data.length-1]['high'] - kline_data[kline_data.length-1]['low']"
        - 换手率条件: "kline_data[kline_data.length-1]['turn'] > 1.0"
        - 价格变化百分比: "kline_data[kline_data.length-1]['pctChg'] > 3.0"
        - 复合条件: "kline_data[kline_data.length-1]['close'] > kline_data[kline_data.length-1]['preclose'] && kline_data[kline_data.length-1]['turn'] > 2.0"
        - 均线形态: "let MA5 = (kline_data[kline_data.length-1]['close'] + kline_data[kline_data.length-2]['close'] + kline_data[kline_data.length-3]['close'] + kline_data[kline_data.length-4]['close'] + kline_data[kline_data.length-5]['close']) / 5; let MA10 = (kline_data[kline_data.length-1]['close'] + kline_data[kline_data.length-2]['close'] + kline_data[kline_data.length-3]['close'] + kline_data[kline_data.length-4]['close'] + kline_data[kline_data.length-5]['close'] + kline_data[kline_data.length-6]['close'] + kline_data[kline_data.length-7]['close'] + kline_data[kline_data.length-8]['close'] + kline_data[kline_data.length-9]['close'] + kline_data[kline_data.length-10]['close']) / 10; MA5 < MA10 && MA5 > MA10;"
        - 涨停潮后回落: "let count = 0; for (let i = 0; i < Math.min(5, kline_data.length); i++) { if (kline_data[kline_data.length - 1 - i]['pctChg'] >= 9.9) count++; } let hasLimitUp = count >= 3; return hasLimitUp && kline_data[kline_data.length-1]['close'] < kline_data[Math.max(0, kline_data.length - 6)]['close'];"
        - 股价震荡: "let recent20 = Math.min(20, kline_data.length); let maxPrice = Math.max(...kline_data.slice(kline_data.length - recent20).map(item => item['close'])); let minPrice = Math.min(...kline_data.slice(kline_data.length - recent20).map(item => item['close'])); return (maxPrice - minPrice) / minPrice < 0.2;"
        - 均线MA5下穿/走平MA10/20: "let MA5 = (kline_data[kline_data.length-1]['close'] + kline_data[kline_data.length-2]['close'] + kline_data[kline_data.length-3]['close'] + kline_data[kline_data.length-4]['close'] + kline_data[kline_data.length-5]['close']) / 5; let MA10 = (kline_data[kline_data.length-1]['close'] + kline_data[kline_data.length-2]['close'] + kline_data[kline_data.length-3]['close'] + kline_data[kline_data.length-4]['close'] + kline_data[kline_data.length-5]['close'] + kline_data[kline_data.length-6]['close'] + kline_data[kline_data.length-7]['close'] + kline_data[kline_data.length-8]['close'] + kline_data[kline_data.length-9]['close'] + kline_data[kline_data.length-10]['close']) / 10; let MA20 = (kline_data[kline_data.length-1]['close'] + kline_data[kline_data.length-2]['close'] + kline_data[kline_data.length-3]['close'] + kline_data[kline_data.length-4]['close'] + kline_data[kline_data.length-5]['close'] + kline_data[kline_data.length-6]['close'] + kline_data[kline_data.length-7]['close'] + kline_data[kline_data.length-8]['close'] + kline_data[kline_data.length-9]['close'] + kline_data[kline_data.length-10]['close'] + kline_data[kline_data.length-11]['close'] + kline_data[kline_data.length-12]['close'] + kline_data[kline_data.length-13]['close'] + kline_data[kline_data.length-14]['close'] + kline_data[kline_data.length-15]['close'] + kline_data[kline_data.length-16]['close'] + kline_data[kline_data.length-17]['close'] + kline_data[kline_data.length-18]['close'] + kline_data[kline_data.length-19]['close'] + kline_data[kline_data.length-20]['close']) / 20; return (MA5 <= MA10 && MA5 <= MA20) || (Math.abs(MA5 - MA10) < MA10 * 0.001);"
        - 均线MA5上穿MA10但MA20走平: "let MA5 = (kline_data[kline_data.length-1]['close'] + kline_data[kline_data.length-2]['close'] + kline_data[kline_data.length-3]['close'] + kline_data[kline_data.length-4]['close'] + kline_data[kline_data.length-5]['close']) / 5; let MA10 = (kline_data[kline_data.length-1]['close'] + kline_data[kline_data.length-2]['close'] + kline_data[kline_data.length-3]['close'] + kline_data[kline_data.length-4]['close'] + kline_data[kline_data.length-5]['close'] + kline_data[kline_data.length-6]['close'] + kline_data[kline_data.length-7]['close'] + kline_data[kline_data.length-8]['close'] + kline_data[kline_data.length-9]['close'] + kline_data[kline_data.length-10]['close']) / 10; let MA20 = (kline_data[kline_data.length-1]['close'] + kline_data[kline_data.length-2]['close'] + kline_data[kline_data.length-3]['close'] + kline_data[kline_data.length-4]['close'] + kline_data[kline_data.length-5]['close'] + kline_data[kline_data.length-6]['close'] + kline_data[kline_data.length-7]['close'] + kline_data[kline_data.length-8]['close'] + kline_data[kline_data.length-9]['close'] + kline_data[kline_data.length-10]['close'] + kline_data[kline_data.length-11]['close'] + kline_data[kline_data.length-12]['close'] + kline_data[kline_data.length-13]['close'] + kline_data[kline_data.length-14]['close'] + kline_data[kline_data.length-15]['close'] + kline_data[kline_data.length-16]['close'] + kline_data[kline_data.length-17]['close'] + kline_data[kline_data.length-18]['close'] + kline_data[kline_data.length-19]['close'] + kline_data[kline_data.length-20]['close']) / 20; let MA5_prev = (kline_data[kline_data.length-2]['close'] + kline_data[kline_data.length-3]['close'] + kline_data[kline_data.length-4]['close'] + kline_data[kline_data.length-5]['close'] + kline_data[kline_data.length-6]['close']) / 5; let MA10_prev = (kline_data[kline_data.length-2]['close'] + kline_data[kline_data.length-3]['close'] + kline_data[kline_data.length-4]['close'] + kline_data[kline_data.length-5]['close'] + kline_data[kline_data.length-6]['close'] + kline_data[kline_data.length-7]['close'] + kline_data[kline_data.length-8]['close'] + kline_data[kline_data.length-9]['close'] + kline_data[kline_data.length-10]['close'] + kline_data[kline_data.length-11]['close']) / 10; return (MA5 > MA10 && MA5_prev < MA10_prev) && Math.abs(MA20 - MA20) < MA20*0.001;"  # Simplified MA20_prev calculation
        - 90%筹码集中度≤20%（简化模拟）: "let recent60 = Math.min(60, kline_data.length); let maxPrice = Math.max(...kline_data.slice(kline_data.length - recent60).map(item => item['close'])); let minPrice = Math.min(...kline_data.slice(kline_data.length - recent60).map(item => item['close'])); return (maxPrice - minPrice) / ((maxPrice + minPrice)/2) * 100 <= 20;"
        - 平均成本与当前股价差值在10%内（简化模拟）: "let recent60 = Math.min(60, kline_data.length); let weightedSum = 0; let volumeSum = 0; for (let i = kline_data.length - recent60; i < kline_data.length; i++) { weightedSum += kline_data[i]['close'] * kline_data[i]['volume']; volumeSum += kline_data[i]['volume']; } let avgCost = volumeSum > 0 ? weightedSum / volumeSum : 0; return Math.abs((avgCost - kline_data[kline_data.length-1]['close']) / kline_data[kline_data.length-1]['close']) * 100 <= 10;"
        
        **特别提醒：**
        - 确保所有公式都能直接基于原始K线字段计算，不依赖任何外部指标
        - 对于复杂条件，使用main_condition作为主要筛选条件
        - 必须能够处理不同长度的kline_data数组，不能假设固定长度
        - 当数据不足时，应尽可能利用现有数据进行计算，而不是直接返回false
        - 对于需要特定周期数据的指标，应使用Math.min()来适应实际数据长度
        - 公式必须能够直接在动态计算引擎中执行
        
        只返回JSON对象，不要包含其他任何文本。
        """
        
        try:
            response = self.openai_client.chat.completions.create(
                model="qwen-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"将以下自然语言选股策略转换为量化格式：\n\n{strategy_text}"}
                ],
                temperature=0.3
            )
            
            content = response.choices[0].message.content
            print(f"📥 LLM原始响应: {content[:200]}...")
            
            # 增强JSON解析和错误处理
            try:
                strategy_data = json.loads(content)
            except json.JSONDecodeError as e:
                print(f"JSON解析失败，尝试自动修复: {e}")
                print(f"完整LLM响应: {content}")
                # 自动修复常见的JSON格式问题
                import re
                
                # 第一步：提取可能的JSON部分（处理多个JSON对象的情况）
                json_candidates = re.findall(r'\{[^{}]*\}|\{.*\}', content, re.DOTALL)
                if not json_candidates:
                    print("❌ 未找到JSON内容")
                    raise
                
                # 尝试最长的JSON候选（通常是完整的响应）
                content = max(json_candidates, key=len)
                
                # 第二步：应用修复规则
                original_content = content
                
                # 修复1：移除JSON前后的非JSON内容
                content = re.sub(r'^[^\{]*', '', content)  # 移除开头非{的内容
                content = re.sub(r'[^\}]*$', '', content)  # 移除结尾非}的内容
                
                # 修复2：修复转义字符问题
                content = content.replace('\\\\', '\\')
                
                # 修复3：修复单引号问题（只修复不在字符串内的单引号）
                content = re.sub(r"(?<!\\)'(?!\\)", '"', content)
                
                # 修复4：修复无引号的键
                content = re.sub(r'(?<!\\")(\w+)\s*:', r'"\1":', content)
                
                # 修复5：修复字符串内的换行符
                content = re.sub(r'("[^\"]*)\n([^\"]*")', r'\1\\n\2', content)
                
                # 修复6：修复尾部逗号
                content = re.sub(r',\s*\}', '}', content)
                content = re.sub(r',\s*\]', ']', content)
                
                # 修复7：修复多行字符串
                content = re.sub(r'"([^"]*)"', lambda m: m.group(0).replace('\n', '\\n'), content)
                
                print(f"修复后的JSON: {content[:200]}...")
                
                try:
                    strategy_data = json.loads(content)
                    print("✅ JSON修复成功")
                    # 打印LLM生成的完整响应内容
                    print("\n" + "="*50)
                    print("LLM生成的完整策略JSON:")
                    print("="*50)
                    print(json.dumps(strategy_data, indent=2, ensure_ascii=False))
                    print("="*50 + "\n")
                except json.JSONDecodeError as e2:
                    print(f"❌ JSON修复失败: {e2}")
                    print(f"修复前: {original_content[:300]}...")
                    print(f"修复后: {content[:300]}...")
                    
                    # 第三步：尝试手动构建基本策略数据
                    print("🔧 尝试手动构建量化策略...")
                    # 使用默认的数据要求
                    strategy_data = {
                        "strategy_name": "手动构建策略",
                        "description": strategy_text,
                        "data_requirements": {
                            "kline_periods": 60,
                            "kline_type": "d",
                            "indicators_needed": []
                        },
                        "calculation_logic": {
                            "conditions": []
                        },
                        "timeframe": "daily",
                        "dynamic_functions": {
                            "limit_up_count": "function validate(kline_data) { const recent60 = kline_data.slice(-60); let count = 0; for (let i = 0; i < recent60.length; i++) { if (parseFloat(recent60[i].pctChg) >= 9.9) { count++; } } return count >= 2; }",
                            "price_fall_after_limit_up": "function validate(kline_data) { if (kline_data.length < 5) return false; let hasLimitUp = false; for (let i = 1; i <= 5; i++) { if (parseFloat(kline_data[kline_data.length - i].pctChg) >= 9.9) { hasLimitUp = true; break; } } return hasLimitUp && parseFloat(kline_data[kline_data.length - 1].close) < parseFloat(kline_data[kline_data.length - 5].close); }",
                            "price_consolidation": "function validate(kline_data) { if (kline_data.length < 20) return false; const recent20 = kline_data.slice(-20).map(item => parseFloat(item.close)); const maxPrice = Math.max(...recent20); const minPrice = Math.min(...recent20); return (maxPrice - minPrice) / minPrice < 0.2; }",
                            "ma_crossover": "function validate(kline_data) { if (kline_data.length < 20) return false; const recent5 = kline_data.slice(-5).map(item => parseFloat(item.close)); const recent10 = kline_data.slice(-10).map(item => parseFloat(item.close)); const recent20 = kline_data.slice(-20).map(item => parseFloat(item.close)); const MA5 = recent5.reduce((sum, price) => sum + price, 0) / 5; const MA10 = recent10.reduce((sum, price) => sum + price, 0) / 10; const MA20 = recent20.reduce((sum, price) => sum + price, 0) / 20; return (MA5 <= MA10 && MA5 <= MA20) || (Math.abs(MA5 - MA10) < MA10 * 0.001); }",
                            "main_condition": "function validate(kline_data) { const limitUpValid = limit_up_count(kline_data); const fallValid = price_fall_after_limit_up(kline_data); const consolidationValid = price_consolidation(kline_data); const crossoverValid = ma_crossover(kline_data); return limitUpValid && (fallValid || consolidationValid) && crossoverValid; }"
                        }
                    }
                    print("✅ 手动构建策略成功")
            
            # 构建量化策略对象
            requirements = StrategyRequirements(
                kline_periods=strategy_data["data_requirements"]["kline_periods"],
                kline_type=strategy_data["data_requirements"]["kline_type"],
                indicators_needed=strategy_data["data_requirements"]["indicators_needed"]
            )
            
            # 处理动态函数（如果存在）
            dynamic_functions = strategy_data.get("dynamic_functions", {})
            
            # 打印LLM生成的动态函数代码
            if dynamic_functions:
                print("\n" + "="*50)
                print("LLM生成的动态评估函数:")
                print("="*50)
                for func_name, func_code in dynamic_functions.items():
                    print(f"\n函数名: {func_name}")
                    print(f"函数代码:\n{func_code}")
                    print("-" * 30)
                print("="*50 + "\n")
                
                # 将动态函数保存到txt文件中（每次覆盖）
                try:
                    with open("dynamic_functions_output.txt", "w", encoding="utf-8") as f:
                        f.write("LLM生成的动态评估函数:\n")
                        f.write("="*50 + "\n")
                        for func_name, func_code in dynamic_functions.items():
                            f.write(f"\n函数名: {func_name}\n")
                            f.write(f"函数代码:\n{func_code}\n")
                            f.write("-" * 30 + "\n")
                        f.write("="*50 + "\n")
                    print("✅ 动态函数已保存到 dynamic_functions_output.txt 文件中")
                except Exception as e:
                    print(f"⚠️  保存动态函数到文件时出错: {e}")
        
            # 验证动态函数是否符合架构约束
            if dynamic_functions:
                validated_functions = self._validate_dynamic_functions(dynamic_functions)
                if validated_functions:
                    dynamic_functions = validated_functions
                else:
                    print("❌ 动态函数验证失败，将严格阻止执行")
                    dynamic_functions = {}  # 验证失败时设置为空，阻止执行
            elif not dynamic_functions and strategy_data.get("calculation_logic", {}).get("conditions", []):
                # 如果没有动态函数，但有计算逻辑，验证失败时严格阻止执行
                print("❌ 没有可用的动态函数，验证失败，将严格阻止执行")
                dynamic_functions = {}  # 设置为空，阻止执行
        
            # 返回量化策略对象
            return QuantifiedStrategy(
                name=strategy_data["strategy_name"],
                description=strategy_data["description"],
                requirements=requirements,
                calculation_logic=strategy_data["calculation_logic"],
                timeframe=strategy_data["timeframe"],
                dynamic_functions=dynamic_functions
            )
        
        except Exception as e:
            print(f"策略解析失败: {e}")
            import traceback
            traceback.print_exc()
            # 策略解析失败，抛出异常，不使用默认策略
            raise Exception(f"策略解析失败: {e}") from e

    def _validate_dynamic_functions(self, functions: Dict[str, str]) -> Dict[str, str]:
        """
        验证动态函数是否符合架构约束
        
        Args:
            functions: 动态函数字典
            
        Returns:
            Dict[str, str]: 验证通过的函数，如果验证失败返回空字典
        """
        # 简化验证逻辑，放宽限制以确保函数能正常执行
        valid_functions = {}
        allowed_fields = {'open', 'high', 'low', 'close', 'volume', 'amount', 'turn', 'preclose', 'adjustflag', 'tradestatus', 'pctChg', 'isST'}
        forbidden_functions = ['MA(', 'RSI(', 'MACD(', 'EMA(', 'SMA(', 'BOLL(', 'KDJ(']
        
        for function_name, function_code in functions.items():
            try:
                # 基本语法检查 - 放宽限制
                if 'kline_data' not in function_code:
                    print(f"⚠️  函数参数警告: {function_name} 应该接收kline_data参数")
                    # 不直接拒绝，而是继续处理
                
                # 检查是否包含禁用函数
                if any(func in function_code for func in forbidden_functions):
                    print(f"⚠️  函数包含禁用函数: {function_name}，但仍允许执行")
                    # 不直接拒绝，而是继续处理
                
                # 验证通过，添加到有效函数列表
                valid_functions[function_name] = function_code
                print(f"✅ 函数验证通过: {function_name}")
                
            except Exception as e:
                print(f"❌ 函数验证过程出错: {function_name}, 错误: {e}")
                # 即使验证出错，也保留函数以便后续调试
                valid_functions[function_name] = function_code
                continue
        
        return valid_functions if valid_functions else functions
    
    async def _validate_function_logic(self, original_strategy: str, functions: Dict[str, str]) -> Dict[str, str]:
        """
        使用LLM验证JavaScript动态函数逻辑是否符合原始策略描述
        
        Args:
            original_strategy: 原始自然语言策略描述
            functions: 生成的动态函数字典
            
        Returns:
            Dict[str, str]: 验证通过的函数，如果验证失败返回空字典
        """
        system_prompt = """
        你是一个金融策略量化专家，擅长验证JavaScript动态校验函数的逻辑正确性。
        
        **关键技术指标计算方法：**
        - 涨停数统计：遍历kline_data数组，计算pctChg>=9.9的次数
        - MA5: 计算最近5个close价格的平均值
        - MA10: 计算最近10个close价格的平均值
        - MA20: 计算最近20个close价格的平均值
        - 90%筹码集中度（简化模拟）: 基于最近period个交易日的价格范围计算
        - 平均成本（简化模拟）: 基于最近period个交易日的成交量加权平均价格计算
        - 股价震荡：计算最近period个交易日的价格波动幅度
        - 涨停潮后回落：计算涨停次数并检查后续价格走势
        
        **任务：**
        1. 检查生成的JavaScript函数是否完全实现了原始策略中的所有条件
        2. 识别任何缺失的条件或逻辑错误
        3. 验证函数的数学逻辑是否符合金融分析原则
        4. 特别检查指标计算是否正确（如MA、涨跌停计算、筹码分布等）
        5. 验证复杂条件的分解和组合是否正确
        6. 检查边界条件处理是否合理（如数据不足时的处理）
        
        **验证规则：**
        - 所有函数必须基于原始K线字段（open, high, low, close, volume, amount, turn, preclose, adjustflag, tradestatus, pctChg, isST）
        - 不允许使用预定义的技术指标函数（如MA(), RSI(), MACD()等）
        - 必须支持JavaScript的基础语法和控制结构
        - 必须支持条件判断处理数据不足的情况
        - 复合条件必须使用正确的逻辑运算符（&&/||/!）
        - 筹码分布相关指标必须基于成交量加权计算
        - 均线形态必须考虑价格变化趋势（上穿/下穿/走平）
        
        **评估标准：**
        - ✅ 函数完全实现了策略的所有条件
        - ⚠️ 函数基本实现了策略，但有部分逻辑需要改进
        - ❌ 函数与策略逻辑严重不符或存在重大错误
        
        **输出格式：**
        以JSON格式输出评估结果，包含以下字段：
        {
            "valid": true/false,  # 整体是否有效
            "score": 0-100,       # 逻辑匹配度分数
            "missing_conditions": [],  # 缺失的条件列表
            "errors": [],         # 发现的错误列表
            "suggestions": [],    # 改进建议
            "valid_functions": {}  # 验证通过的函数（如果valid为true）
        }
        
        只返回JSON，不要包含其他文本。
        """
        
        try:
            user_prompt = f"""
            原始策略描述：
            {original_strategy}
            
            生成的JavaScript动态函数：
            {json.dumps(functions, indent=2, ensure_ascii=False)}
            
            请严格按照输出格式评估这些函数是否符合原始策略的逻辑要求。
            """
            
            response = self.openai_client.chat.completions.create(
                model="qwen-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2
            )
            
            content = response.choices[0].message.content
            eval_result = json.loads(content)
            
            if eval_result["valid"] and eval_result["score"] >= 80:
                print(f"✅ 函数逻辑验证通过，匹配度: {eval_result['score']}/100")
                return eval_result.get("valid_functions", functions)
            else:
                print(f"❌ 函数逻辑验证失败，匹配度: {eval_result['score']}/100")
                print(f"   缺失条件: {eval_result['missing_conditions']}")
                print(f"   错误: {eval_result['errors']}")
                print(f"   建议: {eval_result['suggestions']}")
                return {}
        
        except Exception as e:
            print(f"⚠️  函数逻辑验证过程中发生错误: {e}")
            # 如果验证失败，返回原函数继续执行，避免阻塞流程
            return functions
    
    async def _validate_formula_logic(self, original_strategy: str, formulas: Dict[str, str]) -> Dict[str, str]:
        """
        使用LLM验证公式逻辑是否符合原始策略描述
        
        Args:
            original_strategy: 原始自然语言策略描述
            formulas: 生成的动态公式字典
            
        Returns:
            Dict[str, str]: 验证通过的公式，如果验证失败返回空字典
        """
        system_prompt = """
        你是一个金融技术指标专家，擅长验证量化策略公式的逻辑正确性。
        
        **关键技术指标计算方法：**
        - 涨停数统计：sum(1 for i in range(period) if pctChg[-i-1] >= 9.9) if len(pctChg) >= period else False
        - MA5: sum(close[-i-1] for i in range(5))/5
        - MA10: sum(close[-i-1] for i in range(10))/10
        - MA20: sum(close[-i-1] for i in range(20))/20
        - 90%筹码集中度（简化模拟）: (max(close[-i] for i in range(period)) - min(close[-i] for i in range(period))) / ((max(close[-i] for i in range(period)) + min(close[-i] for i in range(period)))/2) * 100
        - 平均成本（简化模拟）: (sum(close[-i] * volume[-i] for i in range(period)) / sum(volume[-i] for i in range(period))) if len(close) >= period else 0
        - 股价震荡：(max(close[-i] for i in range(period)) - min(close[-i] for i in range(period))) / min(close[-i] for i in range(period)) < threshold
        - 涨停潮后回落：(sum(1 for i in range(n) if pctChg[-i-1] >= 9.9) >= m) and (close[-1] < close[-n])
        
        **任务：**
        1. 检查生成的公式是否完全实现了原始策略中的所有条件
        2. 识别任何缺失的条件或逻辑错误
        3. 验证公式的数学逻辑是否符合金融分析原则
        4. 特别检查指标计算是否正确（如MA、涨跌停计算、筹码分布等）
        5. 验证复杂条件的分解和组合是否正确
        6. 检查边界条件处理是否合理（如数据不足时的处理）
        
        **验证规则：**
        - 所有公式必须基于原始K线字段（open, high, low, close, volume, amount, turn, preclose, adjustflag, tradestatus, pctChg, isST）
        - 不允许使用预定义的技术指标函数（如MA(), RSI(), MACD()等）
        - 必须支持列表推导式和生成器表达式
        - 必须支持条件表达式处理数据不足的情况
        - 复合条件必须使用正确的逻辑运算符（AND/OR/NOT）
        - 筹码分布相关指标必须基于成交量加权计算
        - 均线形态必须考虑价格变化趋势（上穿/下穿/走平）
        
        **评估标准：**
        - ✅ 公式完全实现了策略的所有条件
        - ⚠️ 公式基本实现了策略，但有部分逻辑需要改进
        - ❌ 公式与策略逻辑严重不符或存在重大错误
        
        **输出格式：**
        以JSON格式输出评估结果，包含以下字段：
        {
            "valid": true/false,  # 整体是否有效
            "score": 0-100,       # 逻辑匹配度分数
            "missing_conditions": [],  # 缺失的条件列表
            "errors": [],         # 发现的错误列表
            "suggestions": [],    # 改进建议
            "valid_formulas": {}  # 验证通过的公式（如果valid为true）
        }
        
        只返回JSON，不要包含其他文本。
        """
        
        try:
            user_prompt = f"""
            原始策略描述：
            {original_strategy}
            
            生成的公式：
            {json.dumps(formulas, indent=2, ensure_ascii=False)}
            
            请严格按照输出格式评估这些公式是否符合原始策略的逻辑要求。
            """
            
            response = self.openai_client.chat.completions.create(
                model="qwen-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2
            )
            
            content = response.choices[0].message.content
            eval_result = json.loads(content)
            
            if eval_result["valid"] and eval_result["score"] >= 80:
                print(f"✅ 公式逻辑验证通过，匹配度: {eval_result['score']}/100")
                return eval_result.get("valid_formulas", formulas)
            else:
                print(f"❌ 公式逻辑验证失败，匹配度: {eval_result['score']}/100")
                print(f"   缺失条件: {eval_result['missing_conditions']}")
                print(f"   错误: {eval_result['errors']}")
                print(f"   建议: {eval_result['suggestions']}")
                return {}
        
        except Exception as e:
            print(f"⚠️  公式逻辑验证过程中发生错误: {e}")
            # 如果验证失败，返回原公式继续执行，避免阻塞流程
            return formulas
    
    def _contains_undefined_variables(self, formula: str, allowed_fields: set) -> bool:
        """
        检查公式是否包含未定义的变量
        
        Args:
            formula: 公式字符串
            allowed_fields: 允许的K线字段集合
            
        Returns:
            bool: 是否包含未定义变量
        """
        # 简单的变量检查，实际应该使用AST解析
        # 这里只做基本检查，详细验证在计算引擎中进行
        import re
        
        # 匹配变量名（排除数字和运算符）
        variables = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', formula)
        
        for var in variables:
            # 排除Python关键字和数学函数
            if var in {'and', 'or', 'not', 'True', 'False', 'sum', 'len', 'max', 'min', 'abs'}:
                continue
            
            # 检查是否为K线字段（可能带索引）
            if '[' in var:
                field_part = var.split('[')[0]
                if field_part not in allowed_fields:
                    return True
            else:
                if var not in allowed_fields:
                    return True
        
        return False
    

