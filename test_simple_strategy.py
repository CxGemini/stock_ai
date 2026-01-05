#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from stock_analyzer import StockAnalyzer

async def test_simple_strategy():
    """测试简单策略以验证基本功能"""
    # 创建分析器实例
    analyzer = StockAnalyzer()
    
    # 定义一个简单的策略
    strategy = "选择最近一个月涨幅超过10%的股票"
    
    # 执行分析
    result = await analyzer.analyze_strategy(strategy, limit=3)
    
    print(f"策略: {result['strategy']}")
    print(f"匹配股票数量: {result['total_matched']}")
    print("详细结果:")
    for stock, matched in result['results'].items():
        print(f"  {stock}: {'匹配' if matched else '不匹配'}")

if __name__ == "__main__":
    asyncio.run(test_simple_strategy())