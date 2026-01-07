"""
简化版动态计算引擎 - 只负责解析和执行大模型生成的JavaScript动态校验函数

架构说明：
1. 大模型节点：生成基于K线数据数组的JavaScript动态校验函数
2. 函数解析器：将JavaScript函数转换为可执行的计算函数  
3. 数据上下文：提供K线字段访问接口（open, high, low, close, volume, amount）
4. 计算引擎：执行动态函数计算，不包含技术指标的具体实现逻辑
"""

import operator
from typing import Dict, List, Any, Callable
import json
import hashlib

# 确保安装了PyExecJS库
# pip install PyExecJS
try:
    import execjs
    EXECJS_AVAILABLE = True
except ImportError as e:
    EXECJS_AVAILABLE = False
    execjs = None

# 缓存编译后的JavaScript上下文，避免重复编译
COMPILED_CONTEXT_CACHE = {}


class KlineData:
    """K线数据结构"""
    
    def __init__(self, data: List[Dict[str, Any]]):
        self.data = data
        # 更新支持的字段列表，包括新添加的换手率(turn)等字段
        self.fields = ['open', 'high', 'low', 'close', 'volume', 'amount', 'turn', 'preclose', 'adjustflag', 'tradestatus', 'pctChg', 'isST']
    
    def get_field_value(self, field: str, index: int) -> float:
        """获取指定字段在指定索引的值"""
        if field not in self.fields:
            raise ValueError(f"不支持的字段: {field}")
        
        # 处理负数索引（从末尾开始计数）
        if index < 0:
            index = len(self.data) + index
            if index < 0:
                raise ValueError(f"索引超出范围: {index}")
        
        if index >= len(self.data):
            raise ValueError(f"索引超出范围: {index}")
        
        return float(self.data[index][field])
    
    def get_field_series(self, field: str, start: int, end: int) -> List[float]:
        """获取字段的时间序列"""
        return [self.get_field_value(field, i) for i in range(start, end)]


class FormulaContext:
    """公式计算上下文"""
    
    def __init__(self, kline_data: KlineData, allow_undefined_variables: bool = False):
        self.kline_data = kline_data
        self.variables = {}
        self.allow_undefined_variables = allow_undefined_variables
    
    def get_variable(self, name: str):
        """获取变量值"""
        if name in self.variables:
            return self.variables[name]
        
        # 检查是否为转换后的特殊变量名（如 _5_prev）
        # 如果是，转换回原始形式（如 5_prev）再查找
        import re
        if re.match(r'^_(\d+_prev)$', name):
            original_name = name[1:]  # 去掉开头的下划线
            if original_name in self.variables:
                return self.variables[original_name]
        
        # 检查是否为K线字段名（不带索引）
        if name in self.kline_data.fields:
            # 默认返回最新数据（索引-1）
            return self.kline_data.get_field_value(name, -1)
        
        # 如果允许未定义变量，返回None
        if self.allow_undefined_variables:
            return None
            
        raise ValueError(f"未定义的变量: {name}")
    
    def set_variable(self, name: str, value: Any):
        """设置变量值"""
        self.variables[name] = value


class FunctionParser:
    """函数解析器 - 将JavaScript动态校验函数转换为可执行函数"""
    
    def __init__(self):
        self.functions = {}
    
    def parse_function(self, function_code: str) -> Callable:
        """
        解析JavaScript函数字符串为可执行函数
        
        Args:
            function_code: JavaScript函数代码字符串
            
        Returns:
            Callable: 可执行的Python函数，接收kline_data数组作为参数
        """
        
        def function_func(kline_data: List[Dict[str, Any]]) -> bool:
            """
            动态函数执行函数
            
            Args:
                kline_data: K线数据数组
                
            Returns:
                bool: 函数执行结果（符合条件返回True，否则返回False）
            """
            try:
                # 创建JavaScript执行环境
                ctx = execjs.compile(f"{function_code}")
                
                # 提取函数名
                import re
                func_name = None
                
                # 首先检查函数代码的基本结构
                stripped_code = function_code.strip()
                
                # 1. 处理标准函数定义（有命名）
                # function name() {}
                named_func_match = re.search(r'^\s*function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', function_code, re.DOTALL)
                if named_func_match:
                    func_name = named_func_match.group(1)
                else:
                    # 2. 处理匿名函数定义
                    # function() {}
                    if stripped_code.startswith('function('):
                        # 创建一个包装器来执行匿名函数
                        wrapped_code = f"const temp_func = {function_code}\nfunction temp_validate(kline_data) {{ return temp_func(kline_data); }}"
                        ctx = execjs.compile(wrapped_code)
                        func_name = "temp_validate"
                    # 3. 处理带括号的匿名函数表达式
                    # (function() {})
                    elif stripped_code.startswith('(function'):
                        wrapped_code = f"{function_code}\ntemp_func = {function_code}\nfunction temp_validate(kline_data) {{ return temp_func(kline_data); }}"
                        ctx = execjs.compile(wrapped_code)
                        func_name = "temp_validate"
                    # 4. 处理箭头函数
                    # () => {}
                    elif '=>' in stripped_code:
                        wrapped_code = f"const temp_func = {function_code}\nfunction temp_validate(kline_data) {{ return temp_func(kline_data); }}"
                        ctx = execjs.compile(wrapped_code)
                        func_name = "temp_validate"
                    else:
                        raise ValueError("无法识别函数定义格式")
                
                # 执行JavaScript函数
                result = ctx.call(func_name, kline_data)
                
                # 确保返回值是布尔类型
                result = bool(result)
                
                return result
            except Exception as e:
                return False
        
        return function_func
    
    def parse_multiple_functions(self, functions: Dict[str, str]) -> Dict[str, Callable]:
        """
        解析多个JavaScript函数字符串为可执行函数
        
        Args:
            functions: JavaScript函数字典，键为函数名，值为函数代码
            
        Returns:
            Dict[str, Callable]: 可执行的Python函数字典
        """
        parsed_functions = {}
        
        for name, code in functions.items():
            try:
                parsed_functions[name] = self.parse_function(code)
            except Exception:
                pass
        
        return parsed_functions


class DynamicCalculator:
    """动态计算引擎"""
    
    def __init__(self):
        self.parser = FunctionParser()
        self.compiled_functions: Dict[str, Callable] = {}
    
    def compile_function(self, function_name: str, function_code: str):
        """编译JavaScript动态校验函数"""
        try:
            compiled_func = self.parser.parse_function(function_code)
            self.compiled_functions[function_name] = compiled_func
        except Exception:
            pass
    
    def evaluate_function(self, function_name: str, kline_data: List[Dict[str, Any]]) -> bool:
        """评估JavaScript动态校验函数"""
        if function_name not in self.compiled_functions:
            return False
        
        function = self.compiled_functions[function_name]
        
        try:
            result = function(kline_data)
            return result
        except Exception as e:
            # 当数据不足时，不直接返回False，而是记录日志并返回False
            # 这样可以区分是函数执行错误还是数据不足
            return False
    
    def batch_evaluate(self, functions: Dict[str, str], 
                      kline_data: List[Dict[str, Any]]) -> Dict[str, bool]:
        """
        批量评估多个JavaScript动态校验函数
        
        所有函数在同一个JavaScript执行环境中运行，支持函数间互相调用
        """
        results = {}
        
        try:
            # 合并所有函数代码到同一环境
            all_functions_code = []
            
            for function_name, function_code in functions.items():
                stripped_code = function_code.strip()
                
                # 检查函数类型并进行适当的包装
                import re
                
                # 1. 标准函数定义（有命名）
                named_func_match = re.search(r'^\s*function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', stripped_code, re.DOTALL)
                if named_func_match:
                    all_functions_code.append(stripped_code)
                    # 如果原函数名与指定的函数名不同，创建别名
                    original_name = named_func_match.group(1)
                    if original_name != function_name:
                        all_functions_code.append(f"const {function_name} = {original_name};")
                else:
                    # 2. 匿名函数定义
                    if stripped_code.startswith('function('):
                        all_functions_code.append(f"const {function_name} = {stripped_code}")
                    # 3. 带括号的匿名函数表达式
                    elif stripped_code.startswith('(function'):
                        all_functions_code.append(f"const {function_name} = {stripped_code}")
                    # 4. 箭头函数
                    elif '=>' in stripped_code:
                        all_functions_code.append(f"const {function_name} = {stripped_code}")
                    else:
                        raise ValueError(f"无法识别函数定义格式: {stripped_code[:50]}...")
            
            # 编译合并后的所有函数代码
            combined_code = '\n'.join(all_functions_code)
            
            # 使用代码内容的哈希值作为缓存键
            code_hash = hashlib.md5(combined_code.encode()).hexdigest()
            
            # 检查缓存中是否存在编译后的上下文
            if code_hash in COMPILED_CONTEXT_CACHE:
                ctx = COMPILED_CONTEXT_CACHE[code_hash]
            else:
                ctx = execjs.compile(combined_code)
                COMPILED_CONTEXT_CACHE[code_hash] = ctx  # 缓存编译后的上下文
            
            # 依次执行每个函数
            for function_name in functions.keys():
                try:
                    result = ctx.call(function_name, kline_data)
                    result = bool(result)
                    results[function_name] = result
                except Exception as e:
                    # 当数据不足时，不直接返回False，而是记录日志并返回False
                    # 这样可以区分是函数执行错误还是数据不足
                    results[function_name] = False
        
        except Exception as e:
            # 所有函数都标记为失败
            for function_name in functions.keys():
                results[function_name] = False
        
        return results

    def clear_function_cache(self):
        """清空JavaScript函数编译缓存"""
        global COMPILED_CONTEXT_CACHE
        COMPILED_CONTEXT_CACHE = {}
        print("🗑️ JavaScript函数缓存已清空")


