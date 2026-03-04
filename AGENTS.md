# AGENTS.md - 股票智能分析系统

## 1. 项目概览

### 项目名称
股票智能分析与筛选系统

### 项目主要功能
这是一个智能化的股票分析系统，旨在帮助投资者进行量化分析和决策。主要功能包括：
- 股票数据获取与缓存管理
- 动态策略评估与回测
- 交互式股票筛选器
- 自定义策略编写与执行
- 实时K线数据展示
- 进度条显示（数据拉取和动态函数验证）
- 历史记录功能（缓存10条）

### 仓库地址
本地开发项目，位于 `/Users/geminicx/ai projects/stock_ai`

### 技术栈
- Python 3.x
- FastAPI (Web框架)
- baostock (股票数据API)
- asyncio (异步编程)
- pandas (数据处理)
- 缓存机制 (自定义K线缓存管理器)
- uvicorn (ASGI服务器)
- Jinja2 (模板引擎)

## 2. 目录结构

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

### 重要模块功能说明

#### interactive_stock_filter.py
- 基于FastAPI的Web界面
- 提供交互式股票筛选功能
- 包含进度条显示、历史记录功能
- 修复bug：股票数、缓存数据、股价显示

#### data_fetcher.py
- `DataFetcher`类：负责从baostock API获取股票基础信息和K线数据
- `StockInfo`类：封装股票基本信息（代码、市场、名称等）
- 实现股票列表获取和K线数据获取功能

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

## 3. 开发与运行指引

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
- Web界面默认端口为8001，如需修改请调整`interactive_stock_filter.py`

### 组件开发流程
1. 修改功能模块后，重启应用以查看更改
2. 测试新策略时，可在Web界面输入自然语言描述
3. 使用debug_stock_name.py进行股票名称相关功能调试
4. 缓存数据存储在persistent_cache目录，可定期清理

### 关键开发约定和注意事项
- 所有数据获取应通过DataFetcher进行
- 缓存操作必须通过KlineCacheManager管理
- 动态策略函数执行需考虑安全性
- 异步操作使用async/await模式

## 4. 代码规范

### 基本编码规范
- 使用Python PEP 8编码规范
- 函数和变量使用snake_case命名
- 类名使用CamelCase命名
- 重要的函数和类必须有docstring注释

### 代码组织规范
- 数据获取层与业务逻辑层分离
- 缓存管理独立成模块
- 异步操作统一使用asyncio
- 错误处理使用try-except结构

## 5. 配置与环境

### cache_config.json
- 配置缓存保存月数
- 设置每日更新时间
- 定义缓存过期策略

### 环境要求
- Python 3.8+
- baostock账户（免费注册）
- 网络连接（用于API数据获取）

### 依赖安装
```bash
# 确保安装了必要的依赖包
pip install baostock fastapi uvicorn pandas
```

## 6. 依赖与版本

### 主要依赖库
- `baostock`: 股票数据API接口
- `fastapi`: Web框架
- `uvicorn`: ASGI服务器
- `pandas`: 数据处理
- `asyncio`: 异步编程支持
- `logging`: 日志记录

### 依赖用途简述
- `baostock`: 提供中国股市的历史和实时数据
- `fastapi`: 构建高性能的Web API
- `pandas`: 高效处理和分析股票数据
- `asyncio`: 提高数据获取的并发性能

## 7. 其它经验与最佳实践

### 常见问题与解决方案
- **数据获取失败**: 检查baostock连接状态，确保网络连接正常
- **缓存初始化慢**: 首次启动需要下载大量数据，后续启动会快很多
- **股票名称显示错误**: 使用`get_stock_name`方法获取准确名称
- **策略解析失败**: 检查自然语言描述是否符合预期格式

### 推荐的扩展或二次开发方式

#### 计划中的功能扩展
- **板块数据分析**: 增加行业板块数据，提供板块轮动分析
- **策略保存功能**: 用户可以保存和分享自定义策略
- **金九银十数据**: 集成季节性规律数据，分析特定时期的投资机会

#### 扩展开发建议
- 新增数据源：集成更多股票数据API
- 策略模板：提供常见投资策略的模板
- 回测功能：增加历史数据回测验证功能
- 报告生成：自动生成投资分析报告

#### 性能优化建议
- 增加数据库支持：替换文件缓存为数据库存储
- 分布式计算：支持大规模股票数据并行处理
- CDN加速：静态资源使用CDN提升加载速度

### 项目目标
此项目旨在成为一套完整的量化分析工具，结合人工智能技术，帮助投资者做出更加科学、理性的投资决策。未来计划集成更多高级功能，如机器学习预测模型、风险评估系统等。