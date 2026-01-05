# 股票分析器 (Stock Analyzer)

基于LangGraph和Python的股票策略分析框架，支持自然语言策略输入、个股验证、灰度范围验证和全市场选股功能。

## 项目概述

本项目实现了一个三层架构的股票分析系统：
1. **策略转换层**：将自然语言策略转换为量化策略
2. **数据获取层**：从Baostock API获取股票列表和K线数据
3. **计算分析层**：计算技术指标并验证策略匹配度

## 项目结构

- `stock_analyzer.py`: 主程序入口，实现股票分析逻辑
- `strategy_converter.py`: 策略转换模块，将自然语言转换为量化策略
- `data_fetcher.py`: 数据获取模块，从Baostock获取股票数据
- `dynamic_calculator.py`: 动态计算引擎，支持自定义公式计算
- `test_framework.py`: 测试框架，验证核心功能
- `requirements.txt`: 项目依赖
- `.env`: 环境变量配置
- `setup.sh`: 环境设置脚本
- `run_analyzer.sh`: 股票分析器运行脚本

## 核心功能

1. **自然语言策略输入**：支持用自然语言描述选股策略
2. **个股验证**：针对单个股票代码进行策略验证
3. **灰度范围验证**：限制分析的股票数量，快速验证策略
4. **全市场选股**：对所有股票进行策略筛选
5. **动态公式计算**：支持自定义技术指标公式
6. **性能监控**：记录各层处理时间，优化性能

## 安装和设置

### 方法1：使用setup.sh脚本（推荐）

```bash
# 运行设置脚本
./setup.sh

# 激活虚拟环境
source langgraph-env/bin/activate
```

### 方法2：手动设置

1. 创建虚拟环境：
   ```bash
   python3 -m venv langgraph-env
   ```

2. 激活虚拟环境：
   ```bash
   source langgraph-env/bin/activate
   ```

3. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

## 使用方式

### 命令行参数说明

```
-h, --help            显示帮助信息
--strategy STRATEGY   自然语言选股策略（必填，除非使用--default）
--limit N             限制分析的股票数量（灰度验证模式）
--default             使用默认策略进行分析
--stock CODE          单个股票代码，格式为'600000.SH'或'000001.SZ'
```

### 1. 个股验证

针对单个股票进行策略验证，适合验证策略的准确性：

```bash
# 使用默认策略验证单个股票
python stock_analyzer.py --default --stock 600000.SH

# 使用自定义策略验证单个股票
python stock_analyzer.py --strategy "选择筹码峰较为集中的股票" --stock 000001.SZ
```

### 2. 灰度范围验证

限制分析的股票数量，快速验证策略效果：

```bash
# 使用默认策略分析前5只股票
python stock_analyzer.py --default --limit 5

# 使用自定义策略分析前10只股票
python stock_analyzer.py --strategy "选择筹码峰较为集中的股票，最近两个月有过涨停的" --limit 10
```

### 3. 全市场选股

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

在`.env`文件中配置以下参数：

```
# Qwen API配置
QWEN_API_KEY=your_qwen_api_key
QWEN_BASE_URL=your_qwen_api_base_url

# Baostock配置（可选）
BAOSTOCK_USER=your_baostock_username
BAOSTOCK_PASSWORD=your_baostock_password
```

## 测试

运行测试框架验证核心功能：

```bash
python test_framework.py
```

## 技术栈

- Python 3.10+
- LangGraph
- LangChain
- Baostock API
- AsyncIO
- Argparse
- Dataclasses

## 注意事项

1. 首次运行时会连接到Baostock API获取数据
2. 使用自然语言策略时，确保描述清晰明确
3. 全市场选股可能需要较长时间，请耐心等待
4. 建议先使用灰度验证或个股验证测试策略效果

## 更新日志

- 2025-12-21: 支持个股验证功能，优化测试框架
- 2025-12-20: 实现三层架构，支持动态公式计算
- 2025-12-19: 集成Baostock API，获取真实股票数据
- 2025-12-18: 初始版本，支持自然语言策略输入
