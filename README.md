# 股票智能分析与筛选系统

基于Python的量化分析工具，结合人工智能技术，帮助投资者做出更加科学、理性的投资决策。系统支持自然语言策略输入、交互式Web筛选、数据缓存管理等功能。

## 项目概述

本项目实现了一个完整的股票智能分析系统，包含以下核心组件：

- **策略转换层**：将自然语言策略转换为量化策略
- **数据获取层**：从Baostock API获取股票列表和K线数据
- **计算分析层**：计算技术指标并验证策略匹配度
- **缓存管理层**：持久化K线数据，提高访问效率
- **Web交互层**：提供现代化的Web界面进行交互式筛选

## 项目结构

```
stock_ai/
├── persistent_cache/           # 持久化缓存目录，存储股票K线数据
│   ├── *.cache               # 每个股票的缓存文件
├── .gitignore                # Git忽略配置
├── AGENTS.md                 # 项目开发指南文档
├── README.md                 # 项目说明文档
├── cache_config.json         # 缓存配置文件
├── create_openclaw_config.py # OpenCLaw配置生成工具
├── data_fetcher.py           # 数据获取层，负责获取股票列表和K线数据
├── debug_stock_name.py       # 股票名称调试工具
├── dynamic_calculator.py     # 动态计算器，执行动态策略函数
├── dynamic_functions_output.txt # 动态函数输出记录
├── interactive_stock_filter.py # 交互式股票筛选器主程序
├── kline_cache_manager.py    # K线数据缓存管理器
├── stock_analyzer.py         # 股票分析器核心组件
├── strategy_converter.py     # 策略转换模块，将自然语言转换为量化策略
├── strategy.txt              # 策略示例文件
└── test_*.py                 # 测试脚本集合
```

### 核心模块说明

#### interactive_stock_filter.py
- 基于FastAPI的Web界面
- 支持进度条显示（数据拉取和动态函数验证）
- 实现历史记录功能（缓存10条）
- 修复bug：股票数、缓存数据、股价显示
- 提供交互式股票筛选功能

#### kline_cache_manager.py
- `KlineCacheManager`类：管理K线数据的缓存、存储和更新
- 支持持久化存储和定期更新
- 提供高效的缓存查询接口

#### dynamic_calculator.py
- `DynamicCalculator`类：动态执行由LLM生成的策略函数
- 提供安全的代码执行环境
- 验证和执行用户定义的动态策略

#### strategy_converter.py
- `StrategyConverter`类：将自然语言策略转换为量化策略
- 增强LLM响应处理，增加空值检查
- 支持策略函数逻辑验证和公式逻辑验证

#### stock_analyzer.py
- `StockAnalyzer`类：股票分析器核心，整合数据获取、策略转换、动态计算等功能
- 提供股票筛选和策略评估能力
- 管理整个分析流程

#### data_fetcher.py
- `DataFetcher`类：负责从baostock API获取股票基础信息和K线数据
- `StockInfo`类：封装股票基本信息（代码、市场、名称等）
- 实现股票列表获取和K线数据获取功能

## 核心功能
- **自然语言策略输入**：支持用自然语言描述选股策略
- **交互式Web筛选**：提供直观的网页界面进行策略输入和结果展示
- **进度条显示**：实时显示数据拉取和动态函数验证进度
- **历史记录功能**：缓存最近10条筛选记录，方便回溯
- **数据缓存管理**：持久化K线数据，避免重复API调用
- **逐层过滤**：支持在当前结果基础上继续应用新策略进行过滤
- **回退功能**：可以回退到之前的筛选状态
- **个股验证**：针对单个股票代码进行策略验证
- **灰度范围验证**：限制分析的股票数量，快速验证策略
- **全市场选股**：对所有股票进行策略筛选
- **动态公式计算**：支持自定义技术指标公式
- **性能监控**：记录各层处理时间，优化性能 

## 安装和设置

### 环境准备

```bash
# 确保安装了必要的依赖包
pip install baostock fastapi uvicorn pandas
```

### 启动命令

```bash
# 启动交互式股票筛选器
python interactive_stock_filter.py
```

### 访问应用

- 应用将在 `http://localhost:8001` 启动
- 首次启动会初始化缓存，可能需要几分钟时间

## 使用方式

### 1. Web界面交互

启动Web界面进行交互式股票筛选：

```bash
# 启动Web界面
python interactive_stock_filter.py

# 打开浏览器访问
http://localhost:8001
```

Web界面功能包括：
- **策略输入**：在网页上输入自然语言股票筛选策略
- **进度显示**：实时显示数据拉取和动态函数验证进度
- **历史记录**：查看最近10条筛选记录
- **逐层过滤**：在当前结果基础上继续应用新策略进行过滤
- **回退功能**：可以回退到之前的筛选状态
- **数据缓存**：K线数据缓存避免重复API调用
- **直观界面**：现代化Web界面，易于操作

### 2. 命令行参数说明

#### 个股验证
针对单个股票进行策略验证，适合验证策略的准确性：

```bash
# 使用默认策略验证单个股票
python stock_analyzer.py --default --stock 600000.SH

# 使用自定义策略验证单个股票
python stock_analyzer.py --strategy "选择筹码峰较为集中的股票" --stock 000001.SZ
```

#### 灰度范围验证
限制分析的股票数量，快速验证策略效果：

```bash
# 使用默认策略分析前5只股票
python stock_analyzer.py --default --limit 5

# 使用自定义策略分析前10只股票
python stock_analyzer.py --strategy "选择筹码峰较为集中的股票，最近两个月有过涨停的" --limit 10
```

#### 3. 全市场选股
对所有股票进行策略筛选，找出符合条件的股票：

```bash
# 使用默认策略进行全市场选股
python stock_analyzer.py --default

# 使用自定义策略进行全市场选股
python stock_analyzer.py --strategy "选择筹码峰较为集中的股票"
```

## 输出示例 

### 个股验证输出 
```
📊 策略 1: 选择筹码峰较为集中的股票 
🎯 分析单个股票: 600000.SH 
🚀 获取600000.SH的K线数据... 
✅ main_condition = (high[-1] - low[-1]) / (close[-1] - open[-1]) > 0.7 → False 
✅ entry_signal = high[-1] - low[-1] < 0.5 * (high[-2] - low[-2]) → True 
✅ exit_signal = close[-1] < close[-5] or volume[-1] < volume[-2] * 0.8 → False 

📈 选股报告 
------------------------------------------ 
📋 策略: 选择筹码峰较为集中的股票 
📊 总股票数: 1只 
✅ 符合条件: 0只 
📈 匹配率: 0.00% 
⏰ 分析时间: 2025-12-21 15:29:12 

⚡ 性能报告 
------------------------------------------ 
⏱️  总耗时: 3.41秒 
📝 策略转换耗时: 3.15秒 
📊 数据获取耗时: 0.26秒 
🔍 分析计算耗时: 0.00秒 

📋 股票详细分析 (600000.SH): 
------------------------------------------ 
📊 计算模式: dynamic 
📈 K线数据量: 20 

📊 动态计算结果: 
   main_condition: 
      公式: (high[-1] - low[-1]) / (close[-1] - open[-1]) > 0.7 
      结果: False 
      解读: 不符合条件 
   entry_signal: 
      公式: high[-1] - low[-1] < 0.5 * (high[-2] - low[-2]) 
      结果: True 
      解读: 符合条件 
   exit_signal: 
      公式: close[-1] < close[-5] or volume[-1] < volume[-2] * 0.8 
      结果: False 
      解读: 不符合条件 

🎯 策略匹配: ❌ 不符合
```

### 灰度验证输出 
```
📊 策略 1: 选择筹码峰较为集中的股票 
🔍 灰度验证模式: 仅分析5只股票 
🚀 并发获取5只股票的K线数据... 

📈 选股报告 
------------------------------------------ 
📋 策略: 选择筹码峰较为集中的股票 
📊 总股票数: 5只 
✅ 符合条件: 2只 
📈 匹配率: 40.00% 
⏰ 分析时间: 2025-12-21 15:30:45 

⚡ 性能报告 
------------------------------------------ 
⏱️  总耗时: 4.25秒 
📝 策略转换耗时: 3.18秒 
📊 数据获取耗时: 0.98秒 
🔍 分析计算耗时: 0.09秒 

📋 符合策略的股票 (2只): 
------------------------------------------ 
   000001.SZ - 价格: 15.67, 20日均线: 15.23, 成交量: 12345678 
   000002.SZ - 价格: 23.45, 20日均线: 22.89, 成交量: 98765432
```

## 环境变量配置

在.env文件中配置以下参数：

```bash
# Qwen API配置
QWEN_API_KEY=your_qwen_api_key
QWEN_BASE_URL=your_qwen_api_base_url

# Baostock配置（可选）
BAOSTOCK_USER=your_baostock_username
BAOSTOCK_PASSWORD=your_baostock_password
```

## 测试

运行测试脚本验证核心功能：

```bash
# 运行所有测试
python test_*.py

# 或运行特定测试文件
python test_cache.py
python test_code_format.py
python test_fix.py
```

## 技术栈

- Python 3.8+
- FastAPI (Web框架)
- baostock (股票数据API)
- asyncio (异步编程)
- pandas (数据处理)
- LangChain/LangGraph (可选，用于高级策略转换)
- uvicorn (ASGI服务器)
- Jinja2 (模板引擎)

## 注意事项

- 首次运行时会连接到Baostock API获取数据
- 使用自然语言策略时，确保描述清晰明确
- 全市场选股可能需要较长时间，请耐心等待
- 建议先使用灰度验证或个股验证测试策略效果
- 缓存数据会存储在`persistent_cache`目录，定期清理可释放磁盘空间
- Web界面默认端口为8001，如需修改请调整`interactive_stock_filter.py`

## 更新日志

- 2026-03-05: 优化Web界面，增加进度条显示和历史记录功能
- 2026-03-03: 新增缓存管理模块，实现K线数据持久化
- 2026-02-16: 增强策略转换器，添加LLM响应空值检查
- 2026-01-07: 去除mcp，增加web界面，支持逐层过滤
- 2025-12-21: 支持个股验证功能，优化测试框架
- 2025-12-20: 实现三层架构，支持动态公式计算
- 2025-12-19: 集成Baostock API，获取真实股票数据
- 2025-12-18: 初始版本，支持自然语言策略输入