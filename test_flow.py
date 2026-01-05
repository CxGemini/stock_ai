#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试简化后的股票分析流程
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

async def test_simple_strategy():
    """测试简单策略"""
    # 创建分析器实例
    analyzer = StockAnalyzer()
    
    # 定义一个简单的策略
    strategy = "寻找最近7天内有3天上涨的股票"
    
    # 执行分析
    result = await analyzer.analyze_strategy(strategy, limit=5)
    
    print(f"策略: {result['strategy']}")
    print(f"匹配股票数量: {result['total_matched']}")
    print("详细结果:")
    for stock, matched in result['results'].items():
        print(f"  {stock}: {'匹配' if matched else '不匹配'}")

if __name__ == "__main__":
    asyncio.run(test_simple_strategy())