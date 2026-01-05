"""
股票分析器 - 基于LangGraph和MCP的三层架构实现

架构说明：
1. 策略转换层：StrategyConverter负责将自然语言策略转换为量化策略
2. 数据获取层：DataFetcher负责从MCP获取股票列表和K线数据
3. 计算分析层：StockAnalyzer负责计算技术指标并筛选股票

主文件仅负责串联这三个层次，不包含具体的实现细节
"""

import os
import json
import asyncio
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('stock_analyzer.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 导入动态计算引擎
try:
    from dynamic_calculator import DynamicCalculator, KlineData, FormulaContext
except ImportError:
    print("⚠️  动态计算引擎未找到，将使用静态计算模式")

# 导入其他层次的组件
from strategy_converter import StrategyConverter
from data_fetcher import DataFetcher

# 导入datetime模块
import datetime

# 加载环境变量
load_dotenv()


@dataclass
class TechnicalIndicators:
    """技术指标计算结果"""
    price: float
    moving_average_20: Optional[float] = None
    average_volume_30: Optional[float] = None
    volume: Optional[float] = None
    rsi: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "Price": self.price,
            "MA_20": self.moving_average_20,
            "Average_Volume_30": self.average_volume_30,
            "Volume": self.volume,
            "RSI": self.rsi
        }


class StockAnalyzer:
    """
    股票分析器主类 - 负责串联策略转换、数据获取和计算分析三个层次
    """
    
    @staticmethod
    def safe_float(s):
        """安全转换浮点数，处理空字符串和其他异常情况"""
        try:
            if s == '' or s is None:
                return 0.0
            return float(s)
        except (ValueError, TypeError):
            return 0.0
    
    def __init__(self):
        """初始化分析器组件"""
        logger.info("初始化StockAnalyzer组件")
        # 初始化LangGraph模型
        self.langgraph_model = ChatOpenAI(
            model="qwen-turbo",
            api_key=os.getenv("QWEN_API_KEY"),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        
        # 初始化各层次组件
        logger.info("初始化策略转换组件")
        self.strategy_converter = StrategyConverter()
        logger.info("初始化数据获取组件")
        self.data_fetcher = DataFetcher(self.langgraph_model)
        
        # 初始化动态计算引擎
        try:
            logger.info("初始化动态计算引擎")
            self.dynamic_calculator = DynamicCalculator()
            self.has_dynamic_calculator = True
            logger.info("动态计算引擎初始化成功")
        except Exception as e:
            logger.error(f"动态计算引擎初始化失败: {e}")
            self.dynamic_calculator = None
            self.has_dynamic_calculator = False
    
    def calculate_indicators(self, kline_data: List[Dict[str, Any]]) -> TechnicalIndicators:
        """
        计算技术指标
        
        Args:
            kline_data: K线数据
            
        Returns:
            TechnicalIndicators: 技术指标计算结果
        """
        logger.info(f"开始计算技术指标，K线数据长度: {len(kline_data)}")
        
        if not kline_data:
            logger.warning("K线数据为空，返回默认指标")
            return TechnicalIndicators(price=0.0)
        
        # 提取收盘价和成交量数据
        closes = [self.safe_float(item["close"]) for item in kline_data]
        volumes = [self.safe_float(item["volume"]) for item in kline_data]
        
        indicators = TechnicalIndicators(price=closes[-1] if closes else 0.0)
        logger.info(f"当前价格: {indicators.price}")
        
        # 计算移动平均线
        if len(closes) >= 20:
            indicators.moving_average_20 = sum(closes[-20:]) / 20
            logger.info(f"计算MA20: {indicators.moving_average_20}")
        else:
            logger.info("K线数据不足20条，跳过MA20计算")
        
        # 计算成交量相关指标
        if len(volumes) >= 30:
            indicators.average_volume_30 = sum(volumes[-30:]) / 30
            indicators.volume = volumes[-1] if volumes else 0
            logger.info(f"计算成交量指标 - 平均成交量(30天): {indicators.average_volume_30}, 当日成交量: {indicators.volume}")
        else:
            logger.info("K线数据不足30条，跳过成交量指标计算")
        
        # 计算RSI（简化版本）
        if len(closes) >= 15:
            gains, losses = [], []
            for i in range(1, min(15, len(closes))):
                change = closes[-i] - closes[-i-1]
                if change > 0:
                    gains.append(change)
                else:
                    losses.append(abs(change))
            
            avg_gain = sum(gains) / len(gains) if gains else 0
            avg_loss = sum(losses) / len(losses) if losses else 0
            
            if avg_loss == 0:
                indicators.rsi = 100
            else:
                rs = avg_gain / avg_loss
                indicators.rsi = 100 - (100 / (1 + rs))
            logger.info(f"计算RSI: {indicators.rsi}")
        else:
            logger.info("K线数据不足15条，跳过RSI计算")
        
        logger.info(f"技术指标计算完成: {indicators.to_dict()}")
        return indicators
    
    async def analyze_strategy(self, strategy_text: str, limit: int = None) -> Dict[str, Any]:
        """
        执行完整的股票分析流程
        
        Args:
            strategy_text: 自然语言策略描述
            limit: 限制分析的股票数量，None表示分析所有股票
            
        Returns:
            Dict: 分析结果
        """

    async def analyze_single_stock(self, strategy_text: str, stock_code: str) -> Dict[str, Any]:
        """
        分析单个股票
        
        Args:
            strategy_text: 自然语言策略描述
            stock_code: 股票代码，格式为"600000.SH"或"000001.SZ"
            
        Returns:
            Dict: 分析结果
        """
        # 第一层：策略转换
        strategy = await self.strategy_converter.parse_natural_language_strategy(strategy_text)
        
        # 解析股票代码
        if "." in stock_code:
            code, market = stock_code.split(".")
            # 创建单个股票的StockInfo对象
            from data_fetcher import StockInfo
            stock = StockInfo(code=code, market=market.lower())
            stocks = [stock]
        else:
            raise ValueError(f"股票代码格式不正确，请使用'600000.SH'或'000001.SZ'格式")
        
        analysis_results = {}
        
        # 记录各层耗时
        performance_data = {
            "total_time": 0.0,
            "strategy_conversion_time": 0.0,
            "data_fetch_time": 0.0,
            "analysis_time": 0.0
        }
        
        import time
        start_time = time.time()
        
        # 第一层：策略转换（重新调用以确保计时准确）
        strategy_conversion_start = time.time()
        strategy = await self.strategy_converter.parse_natural_language_strategy(strategy_text)
        performance_data["strategy_conversion_time"] = time.time() - strategy_conversion_start
        
        # 第二层：数据获取
        data_fetch_start = time.time()
        
        # 并发获取该股票的K线数据
        print(f"🚀 获取{stock.full_code}的K线数据...")
        kline_data_dict = await self.data_fetcher.fetch_kline_data_concurrent(
            stocks, 
            strategy.requirements.kline_periods, 
            strategy.requirements.kline_type
        )
        performance_data["data_fetch_time"] = time.time() - data_fetch_start
        
        # 第三层：计算分析
        analysis_start = time.time()
        
        # 检查是否有动态函数
        has_dynamic_functions = strategy.dynamic_functions and len(strategy.dynamic_functions) > 0
        
        # 打印动态函数信息
        print(f"\n🔍 策略 {strategy.name} 的动态函数信息：")
        print(f"   动态函数是否存在: {has_dynamic_functions}")
        print(f"   动态计算器是否可用: {self.has_dynamic_calculator}")
        
        if has_dynamic_functions:
            print(f"LLM动态函数数量: {len(strategy.dynamic_functions)}")
            for func_name, func_code in strategy.dynamic_functions.items():
                print(f" 📋 LLM函数名: {func_name}")
                # 打印完整的函数代码
                print(f"    LLM代码:\n{func_code}\n")
        
        # 遍历所有获取到的K线数据进行分析
        for stock in stocks:
                kline_data = kline_data_dict.get(stock.full_code, [])
                
                if not kline_data:
                    continue
                
                # 仅使用动态函数计算
                if has_dynamic_functions and self.has_dynamic_calculator:
                    # 动态函数计算
                    dynamic_results = self._evaluate_with_dynamic_functions(kline_data, strategy)
                    
                    analysis_results[stock.full_code] = {
                        "kline_data_count": len(kline_data),
                        "calculation_mode": "dynamic",
                        "dynamic_results": dynamic_results,
                        "strategy_match": self._evaluate_dynamic_strategy_match(dynamic_results, strategy)
                    }
                else:
                    # 没有动态函数或动态计算器不可用，跳过分析
                    print(f"⚠️  {stock.full_code}：没有动态函数或动态计算器不可用，跳过分析")
                    print(f"   动态函数存在: {has_dynamic_functions}")
                    print(f"   动态计算器可用: {self.has_dynamic_calculator}")
                    continue
        
        # 记录分析耗时
        performance_data["analysis_time"] = time.time() - analysis_start
        performance_data["total_time"] = time.time() - start_time
        
        # 生成整体选股报告，包含性能数据
        return self._generate_selection_report(analysis_results, stocks, strategy_text, performance_data)

    async def analyze_strategy(self, strategy_text: str, limit: int = None) -> Dict[str, Any]:
        """
        执行完整的股票分析流程
        
        Args:
            strategy_text: 自然语言策略描述
            limit: 限制分析的股票数量，None表示分析所有股票
            
        Returns:
            Dict: 分析结果
        """
        logger.info(f"开始执行策略分析: {strategy_text}")
        if limit:
            logger.info(f"限制分析股票数量: {limit}")
        
        analysis_results = {}
        
        # 记录各层耗时
        performance_data = {
            "total_time": 0.0,
            "strategy_conversion_time": 0.0,
            "data_fetch_time": 0.0,
            "analysis_time": 0.0
        }
        
        import time
        start_time = time.time()
        
        # 第一层：策略转换
        logger.info("开始策略转换层处理")
        strategy_conversion_start = time.time()
        strategy = await self.strategy_converter.parse_natural_language_strategy(strategy_text)
        performance_data["strategy_conversion_time"] = time.time() - strategy_conversion_start
        logger.info(f"策略转换完成，耗时: {performance_data['strategy_conversion_time']:.2f}秒")
        logger.info(f"转换后的策略: {strategy.name}")
        logger.info(f"动态函数数量: {len(strategy.dynamic_functions) if strategy.dynamic_functions else 0}")
        
        # 第二层：数据获取
        logger.info("开始数据获取层处理")
        data_fetch_start = time.time()
        stocks = await self.data_fetcher.get_stock_universe(limit)
        logger.info(f"获取到{len(stocks)}只股票的基础信息")
        
        # 检查是否有动态函数
        has_dynamic_functions = strategy.dynamic_functions and len(strategy.dynamic_functions) > 0
        logger.info(f"是否使用动态函数: {has_dynamic_functions}")
        
        # 并发获取所有股票的K线数据
        logger.info(f"开始并发获取{len(stocks)}只股票的K线数据...")
        kline_data_dict = await self.data_fetcher.fetch_kline_data_concurrent(
            stocks, 
            strategy.requirements.kline_periods, 
            strategy.requirements.kline_type
        )
        performance_data["data_fetch_time"] = time.time() - data_fetch_start
        logger.info(f"K线数据获取完成，耗时: {performance_data['data_fetch_time']:.2f}秒")
        
        # 第三层：计算分析
        logger.info("开始计算分析层处理")
        analysis_start = time.time()
        
        # 遍历所有获取到的K线数据进行分析
        for stock in stocks:
            stock_code = stock.full_code
            logger.info(f"开始分析股票: {stock_code}")
            
            kline_data = kline_data_dict.get(stock_code, [])
            
            if not kline_data:
                logger.warning(f"未获取到{stock_code}的K线数据，跳过分析")
                continue
            
            logger.info(f"获取到{stock_code}的{len(kline_data)}条K线数据")
            
            # 仅使用动态函数计算
            if has_dynamic_functions and self.has_dynamic_calculator:
                logger.info(f"使用动态函数分析{stock_code}")
                # 动态函数计算
                dynamic_results = self._evaluate_with_dynamic_functions(kline_data, strategy)
                
                strategy_match = self._evaluate_dynamic_strategy_match(dynamic_results, strategy)
                logger.info(f"{stock_code}策略匹配结果: {strategy_match}")
                
                analysis_results[stock_code] = {
                    "kline_data_count": len(kline_data),
                    "calculation_mode": "dynamic",
                    "dynamic_results": dynamic_results,
                    "strategy_match": strategy_match
                }
            else:
                logger.warning(f"{stock_code}：没有动态函数或动态计算器不可用，跳过分析")
                continue
        
        # 记录分析耗时
        performance_data["analysis_time"] = time.time() - analysis_start
        performance_data["total_time"] = time.time() - start_time
        logger.info(f"所有股票分析完成，耗时: {performance_data['analysis_time']:.2f}秒")
        
        # 生成整体选股报告，包含性能数据
        logger.info("生成选股报告")
        report = self._generate_selection_report(analysis_results, stocks, strategy_text, performance_data)
        logger.info(f"报告生成完成，符合条件的股票数量: {report['report']['matched_stocks']}")
        
        return report
    
    def _evaluate_with_dynamic_functions(self, kline_data: List[Dict[str, Any]], 
                                      strategy) -> Dict[str, Any]:
        """使用动态函数计算技术指标"""
        logger.info("开始使用动态函数计算技术指标")
        results = {}
        
        if not strategy.dynamic_functions:
            logger.warning("没有可用的动态函数")
            return results
            
        if not self.has_dynamic_calculator:
            logger.warning("动态计算引擎不可用")
            return results
        
        try:
            logger.info(f"准备评估的动态函数数量: {len(strategy.dynamic_functions)}")
            logger.debug(f"动态函数详情: {strategy.dynamic_functions}")
            
            # 批量计算所有动态函数
            dynamic_results = self.dynamic_calculator.batch_evaluate(
                strategy.dynamic_functions, kline_data
            )
            
            logger.info(f"动态函数批量计算完成，结果数量: {len(dynamic_results)}")
            
            # 将结果转换为可读格式
            for function_name, result in dynamic_results.items():
                results[function_name] = {
                    "function": strategy.dynamic_functions[function_name],
                    "result": result,
                    "interpretation": self._interpret_dynamic_result(result)
                }
                logger.info(f"函数 {function_name} 结果: {result}, 解释: {self._interpret_dynamic_result(result)}")
                
        except Exception as e:
            logger.error(f"动态函数计算失败: {e}", exc_info=True)
            results["error"] = str(e)
        
        return results
    
    def _evaluate_dynamic_strategy_match(self, dynamic_results: Dict[str, Any], 
                                        strategy) -> bool:
        """评估动态函数计算结果是否符合策略"""
        logger.info("开始评估动态函数结果与策略匹配")
        
        if "error" in dynamic_results:
            logger.error(f"动态函数计算结果包含错误: {dynamic_results['error']}")
            return False
        
        logger.debug(f"动态函数计算结果: {dynamic_results}")
        
        # 检查主要条件函数的结果
        main_condition = dynamic_results.get("main_condition", {})
        if main_condition and "result" in main_condition:
            result = main_condition["result"]
            # 确保结果是布尔类型
            if isinstance(result, bool):
                logger.info(f"主要条件函数匹配结果: {result}")
                return result
            else:
                logger.warning(f"主要条件函数结果不是布尔类型: {type(result)}, 值: {result}")
        
        logger.info("未找到主要条件函数，检查所有布尔结果")
        
        # 如果没有主要条件，检查所有布尔结果
        boolean_results = []
        for function_name, result_info in dynamic_results.items():
            result = result_info.get("result")
            if isinstance(result, bool):
                boolean_results.append(result)
                logger.info(f"函数 {function_name} 布尔结果: {result}")
        
        if boolean_results:
            # 所有布尔条件都必须满足才返回True
            overall_result = all(boolean_results)
            logger.info(f"所有布尔条件综合结果: {overall_result}")
            return overall_result
        
        logger.warning("未找到任何布尔类型的结果，默认返回False")
        return False
    
    def _interpret_dynamic_result(self, result: Any) -> str:
        """解释动态计算结果"""
        if isinstance(result, bool):
            return "符合条件" if result else "不符合条件"
        elif isinstance(result, (int, float)):
            return f"数值结果: {result:.4f}"
        elif isinstance(result, dict):
            return f"复合指标: {result}"
        else:
            return f"结果类型: {type(result).__name__}"
    
    def _evaluate_strategy_match(self, indicators: TechnicalIndicators, strategy) -> bool:
        """评估股票是否符合策略条件"""
        logger.info(f"评估静态指标与策略匹配: {indicators.to_dict()}")
        # 这里可以根据具体策略条件进行匹配评估
        # 示例：如果策略需要RSI < 30，则检查RSI指标
        result = True  # 简化实现
        logger.info(f"静态指标策略匹配结果: {result}")
        return result
    
    def _generate_selection_report(self, analysis_results: Dict[str, Any], stocks: List, strategy_text: str, performance_data: Dict[str, float] = None) -> Dict[str, Any]:
        """
        生成整体选股报告
        
        Args:
            analysis_results: 详细分析结果
            stocks: 股票列表
            strategy_text: 策略文本
            performance_data: 性能数据字典，包含各层耗时
            
        Returns:
            Dict: 包含整体报告的字典
        """
        if performance_data is None:
            performance_data = {
                "total_time": 0.0,
                "strategy_conversion_time": 0.0,
                "data_fetch_time": 0.0,
                "analysis_time": 0.0
            }
        # 统计信息
        total_stocks = len(analysis_results)
        matched_stocks = [stock for stock, result in analysis_results.items() if result["strategy_match"]]
        match_rate = len(matched_stocks) / total_stocks if total_stocks > 0 else 0
        
        # 过滤出符合策略的股票详细信息
        matched_results = {stock: result for stock, result in analysis_results.items() if result["strategy_match"]}
        
        # 按价格排序（如果有价格信息）
        def get_price(result):
            if "indicators" in result:
                return result["indicators"].get("Price", 0)
            return 0
        
        sorted_matched_stocks = sorted(matched_results.items(), key=lambda x: get_price(x[1]), reverse=True)
        
        # 构建测试脚本期望的结果格式
        test_compatible_results = {}
        for stock, result in analysis_results.items():
            test_compatible_results[stock] = result["strategy_match"]
        
        return {
            "strategy": strategy_text,
            "total_matched": len(matched_stocks),
            "results": test_compatible_results,
            "report": {
                "strategy": strategy_text,
                "total_stocks": total_stocks,
                "matched_stocks": len(matched_stocks),
                "match_rate": f"{match_rate:.2%}",
                "analysis_time": f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            },
            "performance": {
                "total_time": f"{performance_data['total_time']:.2f}秒",
                "strategy_conversion": f"{performance_data['strategy_conversion_time']:.2f}秒",
                "data_fetch": f"{performance_data['data_fetch_time']:.2f}秒",
                "analysis": f"{performance_data['analysis_time']:.2f}秒"
            },
            "matched_stocks": {
                stock: {
                    "kline_data_count": result["kline_data_count"],
                    "calculation_mode": result["calculation_mode"],
                    "indicators": result.get("indicators", {}),
                    "dynamic_results": result.get("dynamic_results", {})
                } for stock, result in sorted_matched_stocks
            },
            "all_results": analysis_results  # 保留完整结果供调试
        }


async def main():
    """主函数 - 支持命令行参数的股票分析器"""
    import argparse
    
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description="股票策略分析器 - 支持自然语言策略输入和灰度验证")
    parser.add_argument("--strategy", type=str, help="自然语言选股策略，如'选择筹码峰较为集中的股票'")
    parser.add_argument("--limit", type=int, default=None, help="限制分析的股票数量（灰度验证模式），默认分析所有股票")
    parser.add_argument("--default", action="store_true", help="使用默认策略进行分析")
    parser.add_argument("--stock", type=str, help="单个股票代码，格式为'600000.SH'或'000001.SZ'，用于验证具体个股")
    
    args = parser.parse_args()
    
    # 检查参数
    if not args.strategy and not args.default:
        parser.error("必须提供--strategy参数或使用--default参数")
    
    analyzer = StockAnalyzer()
    
    # 确定要使用的策略
    if args.default:
        strategies = ["(近60个交易日涨停数≥2次"]
    else:
        strategies = [args.strategy]
    
    for i, strategy in enumerate(strategies, 1):
        try:
            print(f"\n==========================================")
            print(f"📊 策略 {i}: {strategy}")
            
            if args.stock:
                print(f"🎯 分析单个股票: {args.stock}")
                # 分析单个股票
                results = await analyzer.analyze_single_stock(strategy, args.stock)
            else:
                if args.limit:
                    print(f"🔍 灰度验证模式: 仅分析{args.limit}只股票")
                # 分析股票池
                results = await analyzer.analyze_strategy(strategy, limit=args.limit)
            
            print(f"==========================================")
            
            # 显示分析报告
            print(f"\n📈 选股报告")
            print(f"------------------------------------------")
            report = results["report"]
            print(f"📋 策略: {report['strategy']}")
            print(f"📊 总股票数: {report['total_stocks']}只")
            print(f"✅ 符合条件: {report['matched_stocks']}只")
            print(f"📈 匹配率: {report['match_rate']}")
            print(f"⏰ 分析时间: {report['analysis_time']}")
            
            # 显示性能数据
            print(f"\n⚡ 性能报告")
            print(f"------------------------------------------")
            performance = results["performance"]
            print(f"⏱️  总耗时: {performance['total_time']}")
            print(f"📝 策略转换耗时: {performance['strategy_conversion']}")
            print(f"📊 数据获取耗时: {performance['data_fetch']}")
            print(f"🔍 分析计算耗时: {performance['analysis']}")
            
            # 显示详细分析结果
            if args.stock:
                # 单个股票显示更详细的信息
                print(f"\n📋 股票详细分析 ({args.stock}):")
                print(f"------------------------------------------")
                stock_result = results.get("all_results", {}).get(args.stock, {})
                if stock_result:
                    print(f"📊 计算模式: {stock_result.get('calculation_mode', 'N/A')}")
                    print(f"📈 K线数据量: {stock_result.get('kline_data_count', 'N/A')}")
                    
                    # 显示指标信息
                    if "indicators" in stock_result:
                        print(f"\n📊 技术指标:")
                        for indicator, value in stock_result["indicators"].items():
                            print(f"   {indicator}: {value}")
                    
                    # 显示动态计算结果
                    if "dynamic_results" in stock_result:
                        print(f"\n📊 动态计算结果:")
                        for formula_name, result_info in stock_result["dynamic_results"].items():
                            print(f"   {formula_name}:")
                            print(f"      函数: {result_info.get('function', 'N/A')}")
                            print(f"      结果: {result_info.get('result', 'N/A')}")
                            print(f"      解读: {result_info.get('interpretation', 'N/A')}")
                    
                    print(f"\n🎯 策略匹配: {'✅ 符合' if stock_result.get('strategy_match') else '❌ 不符合'}")
            else:
                # 显示符合条件的股票
                if report['matched_stocks'] > 0:
                    print(f"\n📋 符合策略的股票 ({report['matched_stocks']}只):")
                    print(f"------------------------------------------")
                    for stock_code, result in results["matched_stocks"].items():
                        price = result["indicators"].get("Price", "N/A")
                        ma_20 = result["indicators"].get("MA_20", "N/A")
                        volume = result["indicators"].get("Volume", "N/A")
                        print(f"   {stock_code} - 价格: {price}, 20日均线: {ma_20}, 成交量: {volume}")
                else:
                    print(f"\n❌ 没有找到符合策略的股票")
                
        except Exception as e:
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())