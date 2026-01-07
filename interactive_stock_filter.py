"""
交互式股票筛选器 - Web界面
实现策略输入、结果过滤、回退操作和K线数据缓存功能
"""
import asyncio
import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 导入现有的股票分析模块
from stock_analyzer import StockAnalyzer
from data_fetcher import DataFetcher, StockInfo

# 确保真实StockAnalyzer类也有正确的函数签名
original_analyze_strategy = StockAnalyzer.analyze_strategy
async def enhanced_analyze_strategy(self, strategy_text: str, limit: int = None):
    # 调用原始方法，传递limit参数
    return await original_analyze_strategy(self, strategy_text, limit)
StockAnalyzer.analyze_strategy = enhanced_analyze_strategy

original_analyze_single_stock = StockAnalyzer.analyze_single_stock
async def enhanced_analyze_single_stock(self, strategy_text: str, stock_code: str):
    # 调用原始方法
    return await original_analyze_single_stock(self, strategy_text, stock_code)
StockAnalyzer.analyze_single_stock = enhanced_analyze_single_stock

app = FastAPI(title="交互式股票筛选器")

# 挂载静态文件目录
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# 模板目录
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
os.makedirs(templates_dir, exist_ok=True)

class InteractiveStockFilter:
    """交互式股票筛选器，支持策略输入、过滤和回退操作"""
    
    def __init__(self):
        # 初始化分析器
        try:
            self.analyzer = StockAnalyzer()
            self.data_fetcher = DataFetcher()
        except Exception as e:
            logger.error(f"初始化分析器失败: {e}")
            # 使用模拟分析器
            self.analyzer = StockAnalyzer()
            self.data_fetcher = DataFetcher()
        
        # 存储历史状态的栈
        self.history_stack: List[Dict] = []
        
        # 缓存K线数据，避免重复获取
        self.kline_cache: Dict[str, Any] = {}
    
    async def analyze_strategy(self, strategy_text: str, limit: int = None) -> Dict[str, Any]:
        """执行策略分析"""
        try:
            # 执行策略分析
            result = await self.analyzer.analyze_strategy(strategy_text, limit)
            # 将获取的K线数据存入缓存
            if hasattr(self.data_fetcher, 'kline_cache'):
                self.kline_cache.update(self.data_fetcher.kline_cache)
            
            # 检查是否是真实stock_analyzer的结果格式，需要转换为web界面期望的格式
            if 'matched_stocks' in result and 'report' in result:
                # 转换为web界面期望的格式
                web_format_result = self._convert_to_web_format(result, limit)
                return web_format_result
            else:
                # 如果已经是期望格式，直接返回
                return result
        except Exception as e:
            logger.error(f"策略分析失败: {e}")
            return {
                "error": f"策略分析失败: {str(e)}",
                "stocks": [],
                "total_count": 0
            }
    
    def _convert_to_web_format(self, analyzer_result: Dict[str, Any], limit: int = None) -> Dict[str, Any]:
        """将stock_analyzer的结果转换为web界面期望的格式"""
        try:
            # 从matched_stocks中提取股票信息
            matched_stocks_data = analyzer_result.get('matched_stocks', {})
            
            # 构建web界面期望的股票列表格式
            stocks = []
            for stock_code, stock_data in matched_stocks_data.items():
                # 尝试从股票数据中提取价格信息，如果没有则默认为0
                current_price = 0
                if 'indicators' in stock_data and 'Price' in stock_data['indicators']:
                    current_price = stock_data['indicators']['Price']
                elif stock_data.get('dynamic_results'):
                    # 如果有动态结果，尝试从中提取价格
                    dynamic_results = stock_data['dynamic_results']
                    for func_name, func_data in dynamic_results.items():
                        if 'Price' in func_name or 'price' in func_name:
                            current_price = func_data.get('result', 0)
                
                # 提取股票代码和名称（如果有的话）
                # 从股票代码中分离代码和市场
                if '.' in stock_code:
                    code_part = stock_code.split('.')[0]
                    market_part = stock_code.split('.')[1]
                else:
                    code_part = stock_code
                    market_part = ''
                
                stock_info = {
                    "stock_code": code_part,
                    "stock_name": f"股票{code_part}",  # 由于真实数据中可能没有股票名称，使用默认名称
                    "current_price": current_price,
                    "full_code": stock_code
                }
                
                # 如果原始数据中包含股票名称，使用它
                if 'stock_name' in stock_data:
                    stock_info['stock_name'] = stock_data['stock_name']
                
                stocks.append(stock_info)
            
            # 如果limit被指定，只返回前limit个结果
            if limit and limit > 0:
                stocks = stocks[:limit]
            
            return {
                "stocks": stocks,
                "total_count": len(stocks),
                "strategy": analyzer_result.get('strategy', ''),
                "report": analyzer_result.get('report', {}),
                "performance": analyzer_result.get('performance', {})
            }
        except Exception as e:
            logger.error(f"结果格式转换失败: {e}")
            return {
                "error": f"结果格式转换失败: {str(e)}",
                "stocks": [],
                "total_count": 0
            }
    
    def add_to_history(self, strategy: str, results: List[Dict], timestamp: str, stock_codes: List[str] = None):
        """将当前结果添加到历史记录"""
        if stock_codes is None:
            stock_codes = [stock['stock_code'] for stock in results if 'stock_code' in stock]
        history_item = {
            "strategy": strategy,
            "results": results,
            "timestamp": timestamp,
            "stock_codes": stock_codes
        }
        self.history_stack.append(history_item)
    
    def get_previous_results(self, steps_back: int = 1) -> Optional[Dict]:
        """获取历史结果，steps_back表示回退几步"""
        if len(self.history_stack) >= steps_back:
            return self.history_stack[-steps_back]
        return None
    
    def get_current_results(self) -> Optional[Dict[str, Any]]:
        """获取当前结果"""
        if not self.history_stack:
            return None
        current = self.history_stack[-1]
        return {
            "results": current["results"],
            "stock_codes": current["stock_codes"],
            "strategy": current["strategy"],
            "timestamp": current["timestamp"]
        }
    
    def can_go_back(self) -> bool:
        """检查是否可以回退"""
        return len(self.history_stack) > 1
    
    def go_back(self) -> Optional[Dict]:
        """回退到上一步"""
        if self.can_go_back():
            return self.history_stack.pop()  # 移除当前状态，返回到上一个状态
        return None
    
    async def filter_current_results(self, new_strategy: str) -> Dict[str, Any]:
        """在当前结果基础上应用新策略进行过滤"""
        current = self.get_current_results()
        if not current:
            # 如果没有历史结果，执行全新的策略分析
            return await self.analyze_strategy(new_strategy)
        
        # 在当前股票列表基础上应用新策略
        current_stock_codes = current['stock_codes']
        if not current_stock_codes:
            return {
                "error": "当前结果中没有股票可过滤",
                "stocks": [],
                "total_count": 0
            }
        
        try:
            # 为当前股票列表中的每只股票单独分析
            filtered_results = []
            
            for stock_code in current_stock_codes:
                try:
                    # 尝试获取完整股票代码（包含市场后缀）
                    full_stock_code = stock_code
                    if "." not in stock_code:
                        # 如果没有市场后缀，尝试从原始数据中获取
                        original_stock_data = next(
                            (stock for stock in current['results'] 
                             if stock.get('stock_code') == stock_code), 
                            {}
                        )
                        if 'full_code' in original_stock_data:
                            full_stock_code = original_stock_data['full_code']
                        else:
                            # 默认添加SH后缀（如果代码以6开头）或SZ后缀
                            if stock_code.startswith('6'):
                                full_stock_code = f"{stock_code}.SH"
                            else:
                                full_stock_code = f"{stock_code}.SZ"
                    
                    # 检查是否已缓存该股票的K线数据
                    if stock_code in self.kline_cache:
                        # 使用缓存的数据进行分析
                        single_result = await self.analyzer.analyze_single_stock(new_strategy, full_stock_code)
                    else:
                        # 获取K线数据并缓存 if data_fetcher has the method
                        if hasattr(self.data_fetcher, 'get_kline_data'):
                            kline_data = await self.data_fetcher.get_kline_data(full_stock_code)
                            self.kline_cache[stock_code] = kline_data
                        single_result = await self.analyzer.analyze_single_stock(new_strategy, full_stock_code)
                    
                    # 判断是否符合策略 - 检查多种可能的返回格式
                    is_match = False
                    if isinstance(single_result, dict):
                        # 检查不同的键名
                        is_match = (single_result.get('符合策略', False) or 
                                   single_result.get('strategy_match', False) or
                                   single_result.get('符合', False))
                        # 如果返回的是布尔值或包含布尔结果
                        if not is_match and isinstance(single_result, bool):
                            is_match = single_result
                        elif not is_match and 'result' in single_result:
                            is_match = single_result['result']
                    
                    if is_match:
                        # 合并原始数据和新分析结果
                        original_stock_data = next(
                            (stock for stock in current['results'] 
                             if stock.get('stock_code') == stock_code), 
                            {}
                        )
                        merged_result = {**original_stock_data, **single_result}
                        # 确保包含股票代码
                        if 'stock_code' not in merged_result:
                            merged_result['stock_code'] = stock_code
                        filtered_results.append(merged_result)
                except Exception as e:
                    logger.error(f"分析股票 {stock_code} 时出错: {str(e)}")
                    continue
            
            return {
                "stocks": filtered_results,
                "total_count": len(filtered_results),
                "strategy_applied": new_strategy,
                "from_previous_results": True
            }
        except Exception as e:
            logger.error(f"过滤过程失败: {e}")
            return {
                "error": f"过滤过程失败: {str(e)}",
                "stocks": [],
                "total_count": 0
            }

# 创建全局过滤器实例
filter_system = InteractiveStockFilter()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """主页 - 显示交互式筛选界面"""
    current_results = filter_system.get_current_results()
    can_go_back = filter_system.can_go_back()
    
    # 生成HTML页面
    html_content = generate_html_page(current_results, filter_system.history_stack, can_go_back)
    
    return HTMLResponse(content=html_content)

def generate_html_page(current_results: Optional[Dict], history: List[Dict], can_go_back: bool) -> str:
    """生成HTML页面内容"""
    # 历史记录HTML
    history_html = ""
    for i, record in enumerate(reversed(history)):
        strategy_preview = record['strategy'][:50] + "..." if len(record['strategy']) > 50 else record['strategy']
        total_count = record.get('total_count', len(record.get('results', [])))
        history_html += f"""
        <div class="history-item" data-step="{len(history)-i}">
            <div class="history-header">
                <span class="strategy-preview">{strategy_preview}</span>
                <span class="result-count">{total_count} 只股票</span>
                <span class="timestamp">{record['timestamp']}</span>
            </div>
        </div>
        """
    
    # 当前结果HTML
    results_html = ""
    if current_results:
        total_count = current_results.get('total_count', len(current_results.get('results', [])))
        results_html = f"""
        <div class="current-results">
            <h3>当前结果 - {total_count} 只股票</h3>
            <div class="results-list">
        """
        
        stocks = current_results.get('results', [])
        for stock in stocks:
            stock_code = stock.get('stock_code', 'N/A')
            stock_name = stock.get('stock_name', 'N/A')
            price = stock.get('current_price', 'N/A')
            
            results_html += f"""
            <div class="stock-item">
                <div class="stock-info">
                    <span class="stock-code">{stock_code}</span>
                    <span class="stock-name">{stock_name}</span>
                    <span class="stock-price">价格: {price}</span>
                </div>
            </div>
            """
        
        results_html += "</div></div>"
    
    # 构建完整的HTML页面
    html = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>交互式股票筛选器</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            :root {{
                --primary-color: #4361ee;
                --secondary-color: #3f37c9;
                --success-color: #4cc9f0;
                --light-bg: #f8f9fa;
                --dark-text: #212529;
            }}
            
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
                min-height: 100vh;
                padding: 20px;
            }}
            
            .container {{
                max-width: 1400px;
                margin: 0 auto;
            }}
            
            .card {{
                border: none;
                border-radius: 15px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
                overflow: hidden;
                margin-bottom: 25px;
            }}
            
            .header {{
                background: linear-gradient(90deg, var(--primary-color) 0%, var(--secondary-color) 100%);
                color: white;
                padding: 30px;
                text-align: center;
                border-radius: 15px 15px 0 0;
            }}
            
            .main-content {{
                display: grid;
                grid-template-columns: 1fr 2fr;
                gap: 25px;
                padding: 25px;
            }}
            
            @media (max-width: 992px) {{
                .main-content {{
                    grid-template-columns: 1fr;
                }}
            }}
            
            .input-section {{
                background: white;
                padding: 25px;
                border-radius: 15px;
                height: fit-content;
            }}
            
            .form-group {{
                margin-bottom: 25px;
            }}
            
            label {{
                display: block;
                margin-bottom: 10px;
                font-weight: 600;
                color: var(--dark-text);
                font-size: 1.1em;
            }}
            
            textarea {{
                width: 100%;
                padding: 15px;
                border: 2px solid #e1e5eb;
                border-radius: 10px;
                font-size: 1em;
                resize: vertical;
                min-height: 120px;
                transition: border-color 0.3s ease;
            }}
            
            textarea:focus {{
                outline: none;
                border-color: var(--primary-color);
                box-shadow: 0 0 0 3px rgba(67, 97, 238, 0.2);
            }}
            
            .btn {{
                width: 100%;
                padding: 12px;
                border: none;
                border-radius: 8px;
                font-size: 1em;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s ease;
                margin-bottom: 10px;
            }}
            
            .btn-analyze {{
                background: linear-gradient(90deg, var(--primary-color) 0%, var(--secondary-color) 100%);
                color: white;
            }}
            
            .btn-analyze:hover {{
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(67, 97, 238, 0.4);
            }}
            
            .btn-back {{
                background: linear-gradient(90deg, #ff7e5f 0%, #feb47b 100%);
                color: white;
            }}
            
            .btn-back:hover {{
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(255, 126, 95, 0.4);
            }}
            
            .btn-clear {{
                background: #6c757d;
                color: white;
            }}
            
            .btn-clear:hover {{
                background: #5a6268;
            }}
            
            .btn:disabled {{
                opacity: 0.6;
                cursor: not-allowed;
                transform: none;
                box-shadow: none;
            }}
            
            .history-section {{
                background: white;
                padding: 25px;
                border-radius: 15px;
            }}
            
            .section-title {{
                font-size: 1.4em;
                margin-bottom: 20px;
                color: var(--dark-text);
                border-bottom: 2px solid #e1e5eb;
                padding-bottom: 12px;
                display: flex;
                align-items: center;
            }}
            
            .section-title i {{
                margin-right: 10px;
                color: var(--primary-color);
            }}
            
            .history-item {{
                background: var(--light-bg);
                padding: 15px;
                margin-bottom: 12px;
                border-radius: 10px;
                border-left: 4px solid var(--primary-color);
                cursor: pointer;
                transition: all 0.2s ease;
            }}
            
            .history-item:hover {{
                background: #eef2f7;
                transform: translateX(5px);
            }}
            
            .history-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            
            .strategy-preview {{
                font-weight: 500;
                color: var(--secondary-color);
                flex: 1;
            }}
            
            .result-count, .timestamp {{
                font-size: 0.9em;
                color: #666;
            }}
            
            .results-section {{
                background: white;
                padding: 25px;
                border-radius: 15px;
            }}
            
            .current-results {{
                background: var(--light-bg);
                padding: 20px;
                border-radius: 10px;
            }}
            
            .results-list {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
                gap: 15px;
                margin-top: 15px;
            }}
            
            .stock-item {{
                background: white;
                padding: 18px;
                border-radius: 10px;
                border: 1px solid #e1e5eb;
                box-shadow: 0 3px 10px rgba(0,0,0,0.08);
                transition: transform 0.2s ease;
            }}
            
            .stock-item:hover {{
                transform: translateY(-3px);
                box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            }}
            
            .stock-info {{
                display: flex;
                justify-content: space-between;
                flex-wrap: wrap;
            }}
            
            .stock-code {{
                font-weight: bold;
                color: var(--secondary-color);
                font-size: 1.1em;
            }}
            
            .stock-name {{
                color: var(--primary-color);
                font-weight: 500;
            }}
            
            .stock-price {{
                color: #28a745;
                font-weight: 500;
            }}
            
            .error {{
                background: #f8d7da;
                color: #721c24;
                padding: 15px;
                border-radius: 8px;
                margin: 10px 0;
                border: 1px solid #f5c6cb;
            }}
            
            .loading {{
                text-align: center;
                padding: 30px;
            }}
            
            .spinner {{
                border: 4px solid #f3f3f3;
                border-top: 4px solid var(--primary-color);
                border-radius: 50%;
                width: 40px;
                height: 40px;
                animation: spin 1s linear infinite;
                margin: 0 auto 15px;
            }}
            
            @keyframes spin {{
                0% {{ transform: rotate(0deg); }}
                100% {{ transform: rotate(360deg); }}
            }}
            
            .stats-card {{
                background: white;
                padding: 20px;
                border-radius: 15px;
                margin-bottom: 25px;
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
            }}
            
            .stat-item {{
                text-align: center;
                padding: 15px;
                border-radius: 10px;
                background: var(--light-bg);
            }}
            
            .stat-value {{
                font-size: 1.8em;
                font-weight: bold;
                color: var(--primary-color);
                margin-bottom: 5px;
            }}
            
            .stat-label {{
                font-size: 0.9em;
                color: #666;
            }}
            
            .instructions {{
                background: #e7f5ff;
                padding: 20px;
                border-radius: 10px;
                margin-bottom: 25px;
                border-left: 4px solid var(--success-color);
            }}
            
            .instructions h4 {{
                color: var(--primary-color);
                margin-bottom: 10px;
            }}
            
            .instructions ul {{
                padding-left: 20px;
            }}
            
            .instructions li {{
                margin-bottom: 8px;
                color: #495057;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="card">
                <div class="header">
                    <h1><i class="fas fa-filter"></i> 🚀 交互式股票筛选器</h1>
                    <p class="lead">输入策略，逐步筛选，随时回退</p>
                </div>
                
                <div class="stats-card">
                    <div class="stat-item">
                        <div class="stat-value">{len(history)}</div>
                        <div class="stat-label">筛选步骤</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{current_results.get('total_count', 0) if current_results else 0}</div>
                        <div class="stat-label">当前股票</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{len(filter_system.kline_cache)}</div>
                        <div class="stat-label">缓存数据</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{'无' if not history else history[-1]['strategy'][:20] + '...' if len(history[-1]['strategy']) > 20 else history[-1]['strategy']}</div>
                        <div class="stat-label">当前策略</div>
                    </div>
                </div>
                
                <div class="instructions">
                    <h4><i class="fas fa-lightbulb"></i> 使用说明</h4>
                    <ul>
                        <li>在左侧输入股票筛选策略，例如："股价低于20元且市盈率小于15的股票"</li>
                        <li>点击"🔍 分析策略"按钮开始筛选</li>
                        <li>结果会基于当前股票池进行过滤，无需重复获取K线数据</li>
                        <li>可以随时点击"↩️ 回退上一步"返回到之前的筛选结果</li>
                        <li>历史记录会显示每一步的筛选策略和结果数量</li>
                    </ul>
                </div>
                
                <div class="main-content">
                    <div class="input-section">
                        <div class="form-group">
                            <label for="strategy"><i class="fas fa-bullseye"></i> 股票筛选策略</label>
                            <textarea id="strategy" placeholder="请输入您的股票筛选策略，例如：'股价低于20元且市盈率小于15的股票'"></textarea>
                        </div>
                        
                        <button class="btn btn-analyze" onclick="analyzeStrategy()">
                            <i class="fas fa-play-circle"></i> 分析策略
                        </button>
                        <button class="btn btn-back" onclick="goBack()" {'disabled' if not can_go_back else ''}>
                            <i class="fas fa-undo"></i> 回退上一步
                        </button>
                        <button class="btn btn-clear" onclick="clearAll()">
                            <i class="fas fa-trash-alt"></i> 清空所有
                        </button>
                    </div>
                    
                    <div class="history-section">
                        <h3 class="section-title"><i class="fas fa-history"></i> 筛选历史</h3>
                        {history_html if history_html else '<p class="text-muted">暂无历史记录</p>'}
                    </div>
                    
                    <div class="results-section">
                        <h3 class="section-title"><i class="fas fa-chart-bar"></i> 筛选结果</h3>
                        {results_html if results_html else '<p class="text-muted">请在左侧输入策略并点击"分析策略"开始筛选</p>'}
                    </div>
                </div>
            </div>
        </div>
        
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            async function analyzeStrategy() {{
                const strategyInput = document.getElementById('strategy');
                const strategy = strategyInput.value.trim();
                
                if (!strategy) {{
                    alert('请输入筛选策略');
                    return;
                }}
                
                // 显示加载状态
                const resultsSection = document.querySelector('.results-section');
                resultsSection.innerHTML = `
                    <h3 class="section-title"><i class="fas fa-chart-bar"></i> 筛选结果</h3>
                    <div class="loading">
                        <div class="spinner"></div>
                        <p>正在分析策略，请稍候...</p>
                    </div>
                `;
                
                try {{
                    const response = await fetch('/analyze', {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/x-www-form-urlencoded',
                        }},
                        body: 'strategy=' + encodeURIComponent(strategy)
                    }});
                    
                    const data = await response.json();
                    
                    // 重新加载页面以更新所有内容
                    window.location.reload();
                }} catch (error) {{
                    resultsSection.innerHTML = `
                        <h3 class="section-title"><i class="fas fa-chart-bar"></i> 筛选结果</h3>
                        <div class="error">分析失败: ` + error.message + `</div>
                    `;
                }}
            }}
            
            async function goBack() {{
                if (!confirm('确定要回退到上一步吗？当前结果将丢失。')) {{
                    return;
                }}
                
                try {{
                    const response = await fetch('/go_back', {{
                        method: 'POST'
                    }});
                    
                    const data = await response.json();
                    
                    if (data.error) {{
                        alert(data.error);
                    }} else {{
                        // 重新加载页面以更新所有内容
                        window.location.reload();
                    }}
                }} catch (error) {{
                    alert('回退失败: ' + error.message);
                }}
            }}
            
            async function clearAll() {{
                if (!confirm('确定要清空所有历史记录吗？')) {{
                    return;
                }}
                
                try {{
                    const response = await fetch('/clear', {{
                        method: 'POST'
                    }});
                    
                    window.location.reload();
                }} catch (error) {{
                    alert('清空失败: ' + error.message);
                }}
            }}
            
            // 回车键提交（Ctrl+Enter）
            document.getElementById('strategy').addEventListener('keydown', function(e) {{
                if (e.key === 'Enter' && e.ctrlKey) {{
                    analyzeStrategy();
                }}
            }});
        </script>
    </body>
    </html>
    """
    
    return html

@app.post("/analyze")
async def analyze(strategy: str = Form(...), limit: int = Form(None)):
    """分析策略并返回结果"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 如果有历史结果，则在当前结果基础上过滤，否则执行全新分析
    if filter_system.get_current_results():
        result = await filter_system.filter_current_results(strategy)
    else:
        result = await filter_system.analyze_strategy(strategy, limit=limit)
    
    # 只有在没有错误时才添加到历史记录
    if 'error' not in result or not result['error']:
        filter_system.add_to_history(
            strategy=strategy,
            results=result.get('stocks', []),
            timestamp=timestamp,
            stock_codes=[stock.get('stock_code', '') for stock in result.get('stocks', [])]
        )
    
    return result

@app.post("/go_back")
async def go_back():
    """回退到上一步"""
    result = filter_system.go_back()
    if result:
        return result
    else:
        return {"error": "无法回退，已是第一步"}

@app.post("/clear")
async def clear():
    """清空所有历史记录"""
    filter_system.history_stack.clear()
    return {"message": "已清空所有历史记录"}

@app.get("/history")
async def get_history():
    """获取历史记录"""
    return {"history": filter_system.history_stack}

@app.get("/can_go_back")
async def can_go_back():
    """检查是否可以回退"""
    return {"can_go_back": filter_system.can_go_back()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)