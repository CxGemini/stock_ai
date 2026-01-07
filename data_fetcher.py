"""
数据获取层 - 负责获取股票列表和K线数据（原生实现）
"""
import asyncio
import baostock as bs
from typing import List, Dict, Any
from dataclasses import dataclass
import time
from datetime import datetime, timedelta

# 并发控制信号量，限制同时进行的数据请求数量
FETCH_CONCURRENCY_LIMIT = asyncio.Semaphore(15)  # 限制最多15个并发请求

# 数据缓存，避免重复API调用
DATA_CACHE = {}
CACHE_TIMEOUT = timedelta(hours=1)  # 缓存1小时

@dataclass
class StockInfo:
    """股票基本信息"""
    code: str
    market: str
    
    @property
    def full_code(self) -> str:
        """获取完整股票代码"""
        market_upper = self.market.upper()
        if market_upper == "SH":
            return f"{self.code}.SH"
        elif market_upper == "SZ":
            return f"{self.code}.SZ"
        else:
            return f"{self.code}.{market_upper}"

class DataFetcher:
    """
    数据获取器 - 负责获取股票列表和K线数据（原生实现）
    """
    
    def __init__(self, model=None):
        """初始化数据获取器"""
        self.model = model
        # 初始化baostock
        bs.login()
        print("数据获取器初始化成功")
    
    async def get_stock_universe(self, limit: int = None) -> List[StockInfo]:
        """获取股票池（原生实现）
        
        Args:
            limit: 限制返回的股票数量，None表示返回所有股票
        """
        try:
            # 使用baostock API获取股票列表
            import datetime
            import pandas as pd
            
            # 使用昨天的日期以确保有数据
            yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
            target_date = yesterday.strftime("%Y-%m-%d")
            
            # 如果是周末或节假日，可能没有数据，尝试使用最近的工作日
            days_to_try = [0, 1, 2, 3, 4, 5]
            stock_data = []
            
            for days_ago in days_to_try:
                target_date = (datetime.datetime.now() - datetime.timedelta(days=days_ago)).strftime("%Y-%m-%d")
                
                # 调用baostock API获取所有股票列表
                rs = bs.query_all_stock(day=target_date)
                
                if rs.error_code != "0":
                    continue
                else:
                    # 解析数据
                    while rs.next():
                        stock_data.append(rs.get_row_data())
                    
                    if stock_data:
                        break
            
            if stock_data:
                # 转换为DataFrame便于处理
                df = pd.DataFrame(stock_data, columns=rs.fields)
                
                # 确保数据包含code列
                if 'code' in df.columns:
                    code_col = 'code'
                elif len(df.columns) > 0:
                    code_col = df.columns[0]  # 使用第一列作为代码列
                else:
                    code_col = None
                
                if code_col:
                    # 筛选主板股票（根据代码前缀）
                    main_board_stocks = []
                    for _, row in df.iterrows():
                        full_code = row[code_col]
                        if isinstance(full_code, str) and "." in full_code:
                            market, code = full_code.split(".")
                            market = market.lower()
                            
                            # 沪市主板：600xxx, 601xxx, 603xxx, 605xxx
                            # 深市主板：000xxx, 001xxx, 002xxx
                            is_main_board = False
                            if market == "sh":
                                is_main_board = code.startswith(("600", "601", "603", "605"))
                            elif market == "sz":
                                is_main_board = code.startswith(("000", "001", "002"))
                            
                            # 排除指数和非主板股票
                            is_index = (market == "sh" and code.startswith("000")) or (market == "sz" and code.startswith("399"))
                            
                            if is_main_board and not is_index:
                                main_board_stocks.append(StockInfo(code=code, market=market))
                
                # 应用limit参数
                if limit is not None and len(main_board_stocks) > limit:
                    return main_board_stocks[:limit]
                
                return main_board_stocks
        except Exception as e:
            print(f"获取股票列表时出错: {e}")
        
        # 如果无法获取主板股票列表，返回默认股票池
        default_stocks = [
            StockInfo(code="000001", market="sz"),  # 平安银行
            StockInfo(code="600519", market="sh"),  # 贵州茅台
            StockInfo(code="000858", market="sz"),  # 五粮液
            StockInfo(code="601318", market="sh"),  # 中国平安
            StockInfo(code="000002", market="sz"),  # 万科A
            StockInfo(code="000895", market="sz"),  # 双汇发展
            StockInfo(code="002594", market="sz"),  # 比亚迪
            StockInfo(code="600036", market="sh"),  # 招商银行
            StockInfo(code="601398", market="sh"),  # 工商银行
            StockInfo(code="601995", market="sh"),  # 中金公司
            StockInfo(code="000568", market="sz"),  # 泸州老窖
            StockInfo(code="600276", market="sh"),  # 恒瑞医药
            StockInfo(code="600585", market="sh"),  # 海螺水泥
            StockInfo(code="002415", market="sz"),  # 海康威视
            StockInfo(code="002475", market="sz"),  # 立讯精密
            StockInfo(code="000651", market="sz"),  # 格力电器
            StockInfo(code="601628", market="sh"),  # 中国人寿
            StockInfo(code="601336", market="sh"),  # 新华保险
            StockInfo(code="600887", market="sh"),  # 伊利股份
            StockInfo(code="600000", market="sh"),  # 浦发银行
        ]
        
        # 应用limit参数
        if limit is not None and len(default_stocks) > limit:
            return default_stocks[:limit]
        
        return default_stocks
    
    async def fetch_kline_data(self, stock: StockInfo, periods: int, kline_type: str = "d") -> List[Dict[str, Any]]:
        """
        通过bao_stock直接获取股票K线数据，提高性能
        
        Args:
            stock: 股票信息
            periods: K线数据周期数
            kline_type: K线类型 (d:日线, w:周线, m:月线)
            
        Returns:
            List[Dict]: K线数据列表
        """
        # 生成缓存键
        cache_key = f"{stock.full_code}_{periods}_{kline_type}"
        
        # 检查缓存
        if cache_key in DATA_CACHE:
            cached_data, cache_time = DATA_CACHE[cache_key]
            from datetime import datetime
            if datetime.now() - cache_time < CACHE_TIMEOUT:
                print(f"💾 从缓存获取{stock.full_code}的K线数据")
                return cached_data
        
        async with FETCH_CONCURRENCY_LIMIT:  # 限制并发数
            try:
                # 建立与baostock的连接（第一次调用时）
                if not hasattr(self, '_bs_connected') or not self._bs_connected:
                    bs.login()
                    self._bs_connected = True
                    print("✅ 连接到baostock成功")
                
                # 获取当前日期
                from datetime import datetime, timedelta
                end_date = datetime.now().strftime("%Y-%m-%d")
                
                # 计算开始日期，增加10%的缓冲
                buffer_periods = int(periods * 0.1)  # 10% buffer
                total_periods = periods + buffer_periods
                start_date = (datetime.now() - timedelta(days=total_periods)).strftime("%Y-%m-%d")
            
                # 调用baostock API获取K线数据
                print(f"📊 获取{stock.full_code}的K线数据...")
                rs = bs.query_history_k_data_plus(
                    stock.full_code,
                    "date,code,open,high,low,close,volume,turn,pctChg",
                    start_date=start_date,
                    end_date=end_date,
                    frequency=kline_type,
                    adjustflag="3"  # 复权类型：3为未复权
                )
                
                # 处理返回结果
                kline_data = []
                while (rs.error_code == '0') & rs.next():
                    row_data = rs.get_row_data()
                    
                    # 处理可能的空字符串
                    def safe_float(s):
                        return float(s) if s and s != '' else 0.0
                    
                    kline_data.append({
                    "date": row_data[0],
                    "code": row_data[1],
                    "open": safe_float(row_data[2]),
                    "high": safe_float(row_data[3]),
                    "low": safe_float(row_data[4]),
                    "close": safe_float(row_data[5]),
                    "volume": safe_float(row_data[6]),
                    "turn": safe_float(row_data[7]),
                    "pctChg": safe_float(row_data[8])
                })
                
                # 只返回最近的periods条数据
                result = kline_data[-periods:]
                
                # 存储到缓存
                DATA_CACHE[cache_key] = (result, datetime.now())
                
                return result
                
            except Exception as e:
                print(f"获取K线数据失败 ({stock.full_code}): {e}")
                return []
    
    async def fetch_kline_data_concurrent(self, stocks: List[StockInfo], periods: int, kline_type: str = "d") -> Dict[str, List[Dict[str, Any]]]:
        """
        并发获取多只股票的K线数据，提高性能
        
        Args:
            stocks: 股票列表
            periods: K线数据周期数
            kline_type: K线类型 (d:日线, w:周线, m:月线)
            
        Returns:
            Dict[str, List[Dict]]: 股票代码到K线数据的映射
        """
        try:
            # 建立与baostock的连接
            if not hasattr(self, '_bs_connected') or not self._bs_connected:
                bs.login()
                self._bs_connected = True
                print("✅ 连接到baostock成功")
            
            # 创建并发任务列表
            tasks = []
            for stock in stocks:
                task = asyncio.create_task(self.fetch_kline_data(stock, periods, kline_type))
                tasks.append((stock.full_code, task))
            
            # 等待所有任务完成
            results = {}
            for stock_code, task in tasks:
                kline_data = await task
                results[stock_code] = kline_data
            
            return results
            
        except Exception as e:
            print(f"并发获取K线数据失败: {e}")
            return {}
        finally:
            # 关闭baostock连接
            if hasattr(self, '_bs_connected') and self._bs_connected:
                bs.logout()
                self._bs_connected = False
                print("✅ 关闭baostock连接")
    
    def clear_cache(self):
        """清空数据缓存"""
        global DATA_CACHE
        DATA_CACHE = {}
        print("🗑️ 缓存已清空")
    
    def get_cache_stats(self):
        """获取缓存统计信息"""
        return {
            "cache_size": len(DATA_CACHE),
            "cache_keys": list(DATA_CACHE.keys())
        }
