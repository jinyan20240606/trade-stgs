# Freqtrade Strategies 项目分析报告

## 项目概述

这是一个 **[Freqtrade](https://github.com/freqtrade/freqtrade)** 加密货币量化交易策略库，收录了多种免费的买卖策略，供教育和研究使用。要求 Freqtrade 版本 **2022.4 或更新**。

---

## 目录结构

```
freqtrade-strategies/
├── README.md                          # 项目说明文档
├── ANALYSIS.md                        # 本分析文档
├── user_data/
│   ├── hyperopts/
│   │   └── GodStraHo.py              # GodStra 策略的超参优化器
│   └── strategies/
│       ├── *.py                       # 主策略目录（22个策略）
│       ├── berlinguyinca/             # berlinguyinca 贡献的策略集（27个）
│       ├── futures/                   # 期货专用策略（8个）
│       └── lookahead_bias/           # 含前视偏差的教学策略（4个）
```

---

## 策略分类详解

### 1. 主策略目录（`user_data/strategies/`）

共 **22 个策略文件**，涵盖各种技术分析方法：

| 策略文件 | 核心指标/方法 |
|---|---|
| `Strategy001.py` | EMA20/50/100 + 平均K线（Heikinashi） |
| `Strategy002.py` | 基础均线交叉 |
| `Strategy003.py` | 多指标组合 |
| `Strategy004.py` | 多指标组合 |
| `Strategy005.py` | 高频交易优化 |
| `GodStra.py` | 全量 TA 指标 + DNA 超参进化 |
| `Supertrend.py` | 3重 Supertrend 指标（仅做多） |
| `MultiMa.py` | 多均线系统 |
| `Bandtastic.py` | 布林带策略 |
| `PatternRecognition.py` | K线形态识别 |
| `PowerTower.py` | 趋势跟踪 |
| `InformativeSample.py` | 多时间框架信息对示例 |
| `multi_tf.py` | 多时间框架策略 |
| `UniversalMACD.py` | MACD 通用策略 |
| `hlhb.py` | HLHB 趋势系统 |
| `SwingHighToSky.py` | 波段突破策略 |
| `CustomStoplossWithPSAR.py` | 抛物线止损（PSAR）自定义止损 |
| `FixedRiskRewardLoss.py` | 固定风险/回报比止损 |
| `BreakEven.py` | 盈亏平衡止损 |
| `Diamond.py` | 钻石形态策略 |
| `Heracles.py` | 综合趋势策略 |
| `HourBasedStrategy.py` | 基于时间段的策略 |
| `Strategy001_custom_exit.py` | Strategy001 + 自定义退出逻辑 |

---

### 2. berlinguyinca 策略集（`berlinguyinca/`）

共 **27 个策略**，包含经典且广泛使用的策略：

| 策略文件 | 说明 |
|---|---|
| `CombinedBinHAndCluc.py` | 组合 BinHV45 + ClucMay72018，双策略联合信号 |
| `BinHV27.py` | BinH 变体 V27 |
| `BinHV45.py` | BinH 变体 V45（布林带突破） |
| `ClucMay72018.py` | Cluc 布林带 + EMA 策略 |
| `BbandRsi.py` | 布林带 + RSI 组合 |
| `MACDStrategy.py` | 纯 MACD 策略 |
| `MACDStrategy_crossed.py` | MACD 交叉信号策略 |
| `ADXMomentum.py` | ADX 动量策略 |
| `AdxSmas.py` | ADX + 多均线策略 |
| `AverageStrategy.py` | 均值策略 |
| `ReinforcedAverageStrategy.py` | 增强均值回归策略 |
| `ReinforcedQuickie.py` | 增强快速策略 |
| `ReinforcedSmoothScalp.py` | 增强平滑剥头皮策略 |
| `EMASkipPump.py` | EMA + 跳过拉盘过滤 |
| `TDSequentialStrategy.py` | TD 序列形态识别 |
| `TechnicalExampleStrategy.py` | 技术指标示例策略 |
| `CCIStrategy.py` | CCI 指标策略 |
| `MultiRSI.py` | 多重 RSI 策略 |
| `AwesomeMacd.py` | Awesome Oscillator + MACD |
| `CofiBitStrategy.py` | CofiBit 复合策略 |
| `CMCWinner.py` | CMC 趋势策略 |
| `ASDTSRockwellTrading.py` | Rockwell Trading 系统 |
| `Quickie.py` | 快速短线策略 |
| `Scalp.py` | 剥头皮策略 |
| `Simple.py` | 简单指标策略 |
| `SmoothOperator.py` | 平滑算子策略 |
| `SmoothScalp.py` | 平滑剥头皮策略 |
| `Low_BB.py` | 低布林带策略 |
| `DoesNothingStrategy.py` | 空策略（模板用） |
| `Freqtrade_backtest_validation_freqtrade1.py` | 回测验证用策略 |

---

### 3. 期货策略（`futures/`）

共 **8 个期货专用策略**，针对 Binance 合约市场优化，支持**双向交易（做多/做空）**：

| 策略文件 | 说明 |
|---|---|
| `FSupertrendStrategy.py` | 期货 Supertrend（支持做多/做空） |
| `FAdxSmaStrategy.py` | ADX + SMA 期货版 |
| `FOttStrategy.py` | OTT 指标期货版 |
| `FReinforcedStrategy.py` | 增强期货策略 |
| `FSampleStrategy.py` | 期货示例策略 |
| `TrendFollowingStrategy.py` | 趋势跟踪期货策略 |
| `VolatilitySystem.py` | 波动率系统 |

**期货配置特点（来自 `Readme.md`）：**

```json
{
  "trading_mode": "futures",
  "margin_mode": "isolated",
  "stake_currency": "USDT",
  "stake_amount": 100,
  "exchange": { "name": "binance" }
}
```

- 交易所：**Binance Futures**
- 保证金模式：**逐仓（isolated）**
- 计价币：**USDT**
- 支持币对：**70+ 个主流合约**（BTC/ETH/SOL/DOT 等）

---

### 4. 前视偏差教学策略（`lookahead_bias/`）

共 **4 个策略**，**故意包含前视偏差**，用于教学目的——帮助开发者识别常见陷阱：

| 策略文件 | 偏差类型 | 说明 |
|---|---|---|
| `DevilStra.py` | 全局归一化偏差 | `normalize()` 使用 `.min()/.max()` 泄露未来数据 |
| `GodStraNew.py` | 全局归一化偏差 | 同 DevilStra，`normalize()` 使用全量数据 |
| `Zeus.py` | 全局归一化偏差 | 用全局 min/max 标准化 `trend_ichimoku_base` 及 `trend_kst_diff` |
| `wtc.py` | sklearn 归一化偏差 | `MinMaxScaler.fit_transform()` 自动使用绝对最大/最小值 |

> ⚠️ **警告**：这些策略**不可用于实盘或真实回测**，回测结果虚高无效。

---

## 技术架构分析

### 策略基类结构

所有策略均继承自 Freqtrade 的 `IStrategy` 基类，实现三个核心方法：

```python
class MyStrategy(IStrategy):

    INTERFACE_VERSION: int = 3

    # 1. 计算技术指标，添加到 DataFrame
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ...

    # 2. 基于指标生成买入（做多入场）信号
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[(...条件...), 'enter_long'] = 1
        return dataframe

    # 3. 基于指标生成卖出（平仓/做空入场）信号
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[(...条件...), 'exit_long'] = 1
        return dataframe
```

### 核心策略参数说明

| 参数 | 类型 | 说明 |
|---|---|---|
| `minimal_roi` | dict | 分级最小收益率表（按持仓时间递减） |
| `stoploss` | float | 止损比例（负值，如 `-0.10` 表示 -10%） |
| `trailing_stop` | bool | 是否启用追踪止损 |
| `trailing_stop_positive` | float | 盈利状态下的追踪止损偏移 |
| `trailing_stop_positive_offset` | float | 启用盈利追踪止损的触发阈值 |
| `timeframe` | str | K线时间周期（`5m`, `1h`, `12h` 等） |
| `startup_candle_count` | int | 启动时需预热的K线数量 |
| `use_exit_signal` | bool | 是否使用退出信号（而非仅靠 ROI/止损） |
| `exit_profit_only` | bool | 仅在盈利状态才执行退出信号 |
| `process_only_new_candles` | bool | 只在新K线出现时计算指标 |

### 典型策略示例：Strategy001

```
入场条件：
  EMA20 上穿 EMA50（金叉）
  AND 平均K线收盘价 > EMA20
  AND 阳线（收盘 > 开盘）

出场条件：
  EMA50 上穿 EMA100
  AND 平均K线收盘价 < EMA20
  AND 阴线（收盘 < 开盘）

止损：-10%  |  时间框架：5分钟  |  最小ROI：5%（即时），1%（60分钟后）
```

---

## GodStra "DNA 进化" 超参优化系统

这是项目中最具创新性的设计，位于 `GodStra.py` 和 `GodStraHo.py`：

### 设计思路

将策略的交易条件参数化为"基因（Gene）"，通过 Freqtrade 超参优化（Hyperopt）自动搜索最优条件组合。

### GodGenes 基因库

包含 **87 个技术指标**作为候选"基因"，涵盖：
- **成交量指标**：`volume_adi`, `volume_obv`, `volume_mfi` 等
- **波动率指标**：`volatility_atr`, `volatility_bbm`, `volatility_kcc` 等
- **趋势指标**：`trend_macd`, `trend_ema_fast`, `trend_ichimoku_base` 等
- **动量指标**：`momentum_rsi`, `momentum_stoch_rsi`, `momentum_ao` 等

### 操作符系统

每个条件由 **（指标, 操作符, 比较值）** 三元组构成：

| 操作符 | 含义 |
|---|---|
| `>` / `<` / `=` | 指标与另一指标比较 |
| `CA` / `CB` | Crossed Above / Crossed Below（交叉） |
| `>I` / `<I` / `=I` | 指标与整数比较 |
| `>R` / `<R` / `=R` | 指标与实数比较 |
| `D` | 禁用（Disabled） |

### 运行超参优化

```bash
freqtrade hyperopt \
  --hyperopt GodStraHo \
  --hyperopt-loss SharpeHyperOptLossDaily \
  --spaces all \
  --strategy GodStra \
  --config config.json \
  -e 100
```

---

## 使用的技术库

| 库 | 用途 |
|---|---|
| `ta-lib` | 主流技术指标（EMA/MACD/RSI/ATR/Supertrend 等） |
| `ta` | 全量技术指标（GodStra 使用 `add_all_ta_features`） |
| `freqtrade.vendor.qtpylib` | Freqtrade 内置指标（Bollinger Bands、crossed_above 等） |
| `numpy` | 数值计算、数组操作 |
| `pandas` | DataFrame 数据处理 |
| `sklearn` | MinMaxScaler 归一化（部分策略） |
| `skopt` | 超参优化空间定义（Categorical/Integer/Real） |

---

## 历史回测参考数据

> 回测区间：2018-01-10 ~ 2018-01-30，启用 `exit_profit_only`

| 策略 | 交易次数 | 平均盈利 | 总盈利（BTC） | 平均持仓（分钟） |
|---|---|---|---|---|
| Strategy001 | 55 | 0.05% | 0.000121 | 476 |
| Strategy002 | 9 | 3.21% | 0.001148 | 189 |
| Strategy003 | 14 | 1.47% | 0.000817 | 228 |
| Strategy004 | 37 | 0.69% | 0.001021 | 367 |
| Strategy005 | 180 | 1.16% | 0.008276 | 156 |

---

## 如何使用策略

### 安装策略

1. 确保已安装 Freqtrade（版本 ≥ 2022.4）
2. 选择策略文件，复制到你的 `user_data/strategies/` 目录
3. 启动机器人：

```bash
freqtrade trade --strategy Strategy001
```

### 回测策略

```bash
# 简单回测
freqtrade backtesting --strategy Strategy001

# 下载最新数据
freqtrade download-data --days 100
```

### 注意事项

- 部分策略需要额外安装依赖（如 GodStra 需要 `pip install ta`）
- 期货策略需要配置 `trading_mode: futures` 及 `margin_mode: isolated`
- GodStra 建议在 `config.json` 的 `pairlists` 中添加 `AgeFilter`（`min_days_listed: 30`）

---

## 项目亮点总结

| 特点 | 说明 |
|---|---|
| **策略多样性** | 从简单 EMA 交叉到复杂三重 Supertrend，覆盖不同风险偏好 |
| **期货支持** | 专门目录提供双向交易（做多/做空）策略 |
| **教学价值** | `lookahead_bias/` 通过反例帮助开发者识别常见陷阱 |
| **超参进化** | GodStra 系列创新性地将策略条件参数化为"DNA"，自动搜索最优逻辑 |
| **社区贡献** | 接受 PR 和 Issue，包含多位贡献者（berlinguyinca、mablue 等） |
| **接口标准** | 统一使用 `INTERFACE_VERSION = 3`，兼容新版 Freqtrade API |

---

## 免责声明

> 所有策略**仅供教育目的**。请勿使用你无法承担损失的资金进行交易。**作者及所有关联方不对你的交易结果承担任何责任。**  
> 使用前请务必先进行回测，并在模拟（Dry-run）模式下充分验证后，再考虑实盘使用。