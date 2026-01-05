#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试动态函数生成功能
"""

import asyncio
import os
import sys

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from stock_analyzer import StockAnalyzer
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

async def test_complex_strategy():
    """测试复杂策略以触发动态函数生成"""
    # 创建分析器实例
    analyzer = StockAnalyzer()
    
    # 定义一个复杂的策略，应该会触发动态函数生成
    strategy = "选择筹码峰较为集中的股票，最近两个月有过涨停的"
    
    # 执行分析
    result = await analyzer.analyze_strategy(strategy, limit=5)
    
    print(f"策略: {result['strategy']}")
    print(f"匹配股票数量: {result['total_matched']}")
    print("详细结果:")
    for stock, matched in result['results'].items():
        print(f"  {stock}: {'匹配' if matched else '不匹配'}")

if __name__ == "__main__":
    asyncio.run(test_complex_strategy())