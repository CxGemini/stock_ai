"""
数据获取层 - 负责从MCP获取股票列表和K线数据
"""
import json
import asyncio
import baostock as bs
from typing import List, Dict, Any
from dataclasses import dataclass
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage

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
    数据获取器 - 负责从MCP获取股票列表和K线数据
    """
    
    def __init__(self, langgraph_model):
        """初始化数据获取器"""
        self.mcp_client = MultiServerMCPClient(
            {
                "stock-cn-server": {
                    "command": "uv",
                    "args": [
                        "--directory",
                        "/Users/geminicx/ai projects/stock_cn_mcp",
                        "run", 
                        "server.py"
                    ],
                    "transport": "stdio"
                }
            }
        )
        self.langgraph_model = langgraph_model
    
    async def get_stock_universe(self, limit: int = None) -> List[StockInfo]:
        """获取股票池（使用新的沪深主板股票列表工具）
        
        Args:
            limit: 限制返回的股票数量，None表示返回所有股票
        """
        def extract_stock_data(result):
            """从各种可能的结果格式中提取股票数据"""
            # 处理None结果
            if result is None:
                return None
            
            # 处理字典类型结果
            if isinstance(result, dict):
                # 直接包含data字段的格式
                if result.get("code") == 200 and "data" in result:
                    if isinstance(result["data"], list):
                        return result["data"]
                
                # 包含content字段的格式
                elif "content" in result:
                    content = result["content"]
                    
                    # 处理content是字符串的情况
                    if isinstance(content, str):
                        try:
                            content_data = json.loads(content)
                            # 递归处理解析后的内容
                            return extract_stock_data(content_data)
                        except json.JSONDecodeError:
                            # 尝试查找类似JSON的内容
                            import re
                            json_pattern = r'\{[^{}]*\}'
                            match = re.search(json_pattern, content)
                            if match:
                                try:
                                    json_data = json.loads(match.group())
                                    return extract_stock_data(json_data)
                                except json.JSONDecodeError:
                                    pass
                    
                    # 处理content本身是字典或列表的情况
                    else:
                        return extract_stock_data(content)
                
                # 包含stocks、stock_list等字段的格式
                for key in ["stocks", "stock_list", "result", "items", "data"]:
                    if key in result and isinstance(result[key], list):
                        return result[key]
                
                # 处理包含text字段的格式（MCP常见返回格式）
                if "text" in result:
                    text_content = result["text"]
                    
                    try:
                        text_data = json.loads(text_content)
                        return extract_stock_data(text_data)
                    except json.JSONDecodeError:
                        # 尝试查找类似JSON的内容
                        import re
                        json_pattern = r'\{[^{}]*\}'
                        match = re.search(json_pattern, text_content)
                        if match:
                            try:
                                json_data = json.loads(match.group())
                                return extract_stock_data(json_data)
                            except json.JSONDecodeError:
                                pass
                
                # 处理LangGraph代理返回的格式
                if "messages" in result:
                    for message in result["messages"]:
                        if hasattr(message, 'tool_calls') and message.tool_calls:
                            for tool_call in message.tool_calls:
                                if hasattr(tool_call, 'output') and tool_call.output:
                                    try:
                                        output_data = json.loads(tool_call.output)
                                        return extract_stock_data(output_data)
                                    except Exception:
                                        pass
            
            # 处理列表类型结果
            elif isinstance(result, list):
                # 如果列表为空，返回空列表
                if not result:
                    return []
                
                # 处理长度为1的列表，可能是嵌套格式
                if len(result) == 1:
                    first_item = result[0]
                    # 如果第一个元素是字典或列表，递归处理
                    if isinstance(first_item, (dict, list)):
                        return extract_stock_data(first_item)
                    
                # 检查列表中的元素是否是股票数据
                first_item = result[0]
                if isinstance(first_item, dict):
                    # 检查是否包含股票标识字段
                    has_stock_fields = any(key in first_item for key in ["code", "symbol", "full_code", "market"])
                    if has_stock_fields:
                        return result
                    
                    # 检查是否包含content字段
                    elif "content" in first_item:
                        combined_data = []
                        for item in result:
                            if isinstance(item, dict) and "content" in item:
                                item_data = extract_stock_data(item)
                                if isinstance(item_data, list):
                                    combined_data.extend(item_data)
                                elif item_data:
                                    combined_data.append(item_data)
                        return combined_data
                
                # 处理字符串列表
                elif isinstance(first_item, str):
                    combined_data = []
                    for item in result:
                        if isinstance(item, str):
                            try:
                                json_data = json.loads(item)
                                item_data = extract_stock_data(json_data)
                                if isinstance(item_data, list):
                                    combined_data.extend(item_data)
                                elif item_data:
                                    combined_data.append(item_data)
                            except json.JSONDecodeError:
                                pass
                    return combined_data if combined_data else result
            
            # 处理字符串类型结果
            elif isinstance(result, str):
                try:
                    content_data = json.loads(result)
                    return extract_stock_data(content_data)
                except json.JSONDecodeError:
                    # 尝试查找多个JSON对象
                    import re
                    json_objects = re.findall(r'\{[^{}]*\}', result)
                    if json_objects:
                        combined_data = []
                        for obj_str in json_objects:
                            try:
                                obj = json.loads(obj_str)
                                obj_data = extract_stock_data(obj)
                                if isinstance(obj_data, list):
                                    combined_data.extend(obj_data)
                                elif obj_data:
                                    combined_data.append(obj_data)
                            except json.JSONDecodeError:
                                pass
                        return combined_data if combined_data else None
            
            return None
        
        def parse_stock_item(stock):
            """解析单个股票数据为StockInfo对象"""
            if not isinstance(stock, dict):
                return None
            
            # 获取股票代码
            code = stock.get("code", "")
            if code:
                if "." in code:
                    # 处理多种格式："sz.000001", "000001.sz", "sh.600000", "600000.sh"
                    parts = code.split(".")
                    if len(parts) == 2:
                        # 尝试两种可能的顺序
                        if parts[0].lower() in ["sh", "sz"]:
                            market, stock_code = parts
                        else:
                            stock_code, market = parts
                        
                        return StockInfo(code=stock_code, market=market.lower())
                else:
                    # 处理单独代码，使用market字段或根据代码前缀判断
                    market = stock.get("market", "")
                    
                    # 如果没有market字段，根据股票代码前缀判断
                    if not market:
                        if code.startswith("6"):
                            market = "sh"
                        else:
                            market = "sz"
                    
                    return StockInfo(code=code, market=market.lower())
            
            # 尝试从其他字段获取股票代码
            for field in ["symbol", "full_code", "stock_code", "stockid"]:
                full_code = stock.get(field, "")
                if full_code:
                    if "." in full_code:
                        # 处理"000001.sz"格式
                        parts = full_code.split(".", 1)
                        if len(parts) == 2:
                            stock_code, market = parts
                            return StockInfo(code=stock_code, market=market.lower())
                    
                    # 处理纯数字代码
                    if full_code.isdigit():
                        # 根据代码长度和前缀判断市场
                        if len(full_code) == 6:
                            if full_code.startswith("6"):
                                market = "sh"
                            else:
                                market = "sz"
                            return StockInfo(code=full_code, market=market.lower())
            
            return None
        
        try:
            # 直接使用baostock API获取股票列表（绕过有问题的MCP服务器）
            # 建立与baostock的连接
            if not hasattr(self, '_bs_connected') or not self._bs_connected:
                login_result = bs.login()
                if login_result.error_code != "0":
                    pass
                else:
                    self._bs_connected = True
            
            if not hasattr(self, '_bs_connected') or not self._bs_connected:
                # 使用MCP服务器作为备用
                async with self.mcp_client.session("stock-cn-server") as session:
                    tools = await load_mcp_tools(session)
                    
                    # 查找get_main_board_stocks工具
                    main_board_stocks_tool = next((tool for tool in tools if tool.name == "get_main_board_stocks"), None)
                    
                    if main_board_stocks_tool:
                        # 传递limit参数给MCP工具
                        tool_params = {} if limit is None else {"limit": limit}
                        result = await main_board_stocks_tool.ainvoke(tool_params)
                        
                        stock_data = extract_stock_data(result)
                        
                        if stock_data:
                            # 应用limit参数
                            processed_stock_data = stock_data[:limit] if limit is not None else stock_data
                            
                            stock_list = []
                            for i, stock in enumerate(processed_stock_data):
                                stock_info = parse_stock_item(stock)
                                if stock_info:
                                    stock_list.append(stock_info)
                            
                            return stock_list
                    else:
                        pass
            else:
                # 获取当前日期 (使用真实日期，避免使用未来日期)
                import datetime
                import pandas as pd
                
                # 使用昨天的日期以确保有数据
                yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
                end_date = yesterday.strftime("%Y-%m-%d")
                
                # 如果是周末或节假日，可能没有数据，尝试使用最近的工作日
                days_to_try = [0, 1, 2, 3, 4, 5]
                stock_data = []
                
                for days_ago in days_to_try:
                    target_date = (datetime.datetime.now() - datetime.timedelta(days=days_ago)).strftime("%Y-%m-%d")
                    
                    # 调用baostock API获取所有股票列表
                    rs = bs.query_all_stock(day=target_date)
                    
                    if rs.error_code != "0":
                        pass
                    else:
                        # 解析数据
                        while rs.next():
                            stock_data.append(rs.get_row_data())
                        
                        if stock_data:
                            break
                
                if not stock_data:
                    pass
                else:
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
                                    main_board_stocks.append({"code": code, "market": market})
                    
                    # 应用limit参数
                    if limit is not None:
                        main_board_stocks = main_board_stocks[:limit]
                    
                    # 转换为StockInfo对象
                    stock_list = []
                    for stock in main_board_stocks:
                        stock_list.append(StockInfo(code=stock["code"], market=stock["market"]))
                    
                    return stock_list
        except Exception:
            pass
        
        # 如果无法获取主板股票列表，返回默认股票池
        return [
            StockInfo(code="000001", market="sz"),  # 平安银行
            StockInfo(code="600519", market="sh"),  # 贵州茅台
            StockInfo(code="000858", market="sz"),  # 五粮液
            StockInfo(code="601318", market="sh")   # 中国平安
        ]
    
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
        try:
            # 建立与baostock的连接（第一次调用时）
            if not hasattr(self, '_bs_connected') or not self._bs_connected:
                bs.login()
                self._bs_connected = True
                print("✅ 连接到baostock成功")
            
            # 获取当前日期
            import datetime
            end_date = datetime.datetime.now().strftime("%Y-%m-%d")
            
            # 计算开始日期，增加10%的缓冲
            buffer_periods = int(periods * 0.1)  # 10% buffer
            total_periods = periods + buffer_periods
            start_date = (datetime.datetime.now() - datetime.timedelta(days=total_periods)).strftime("%Y-%m-%d")
            
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
            return kline_data[-periods:]
            
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
