#!/bin/zsh
# VolatilitySystemV5 趋势稳定性测试脚本
# 测试策略在不同市场环境下的表现：上行趋势、震荡、下行趋势
# 以及不同的时间周期：7天、14天、30天、90天、180天、365天
#
# 数据范围: 2025-02-25 ~ 2026-02-25 (BTC从84K到65K)
# 市场走势概览:
#   2025-03 ~ 2025-04初: 震荡偏弱 (84K → 82K → 77K)
#   2025-04中 ~ 2025-07中: 强劲上涨 (82K → 115K)
#   2025-07 ~ 2025-09: 高位震荡 (108K ~ 115K)
#   2025-10 ~ 2025-11: 急速下跌 (113K → 83K)
#   2025-12 ~ 2026-01中: 低位震荡 (83K ~ 90K)
#   2026-01下 ~ 2026-02: 持续下跌 (87K → 65K)

set -e

FREQTRADE=".venv/bin/freqtrade"
RESULTS_DIR="user_data/backtest_results/trend_analysis"
mkdir -p "$RESULTS_DIR"

STRATEGY="VolatilitySystemV5"
STRATEGY_PATH="user_data/strategies/futures/"
CONFIG="user_data/config_backtest_futures.json"
TIMEFRAME="1h"

# ==========================================
# 时间段定义 (基于实际2025-2026年BTC市场数据)
# ==========================================

# === 上行趋势周期 (2025年4月中~7月中, BTC 82K → 115K) ===
BULL_7D="20250508-20250515"      # 7天强势上涨 (+10.4%周涨幅)
BULL_14D="20250501-20250515"     # 14天上行趋势
BULL_30D="20250413-20250513"     # 30天牛市行情 (包含+6.8%, +10.1%, +10.4%的周)
BULL_90D="20250413-20250713"     # 90天长期上涨 (82K → 115K)

# === 震荡趋势周期 (2025年12月~2026年1月中, BTC 83K ~ 90K横盘) ===
RANGE_7D="20251210-20251217"     # 7天窄幅震荡 (周涨幅~0%)
RANGE_14D="20251207-20251221"    # 14天盘整
RANGE_30D="20251201-20251231"    # 30天横盘整理
RANGE_90D="20250901-20251130"    # 90天震荡市 (含上下波动)

# === 下行趋势周期 (2025年10月中~11月下旬, BTC 113K → 83K) ===
BEAR_7D="20251109-20251116"      # 7天快速下跌 (-10.0%周跌幅)
BEAR_14D="20251102-20251116"     # 14天下行趋势 (-5.3%, -10.0%)
BEAR_30D="20251019-20251118"     # 30天熊市行情 (连续下跌)
BEAR_90D="20251001-20251230"     # 90天长期下跌波段

# === 混合周期 (包含多种市场环境) ===
MIXED_30D="20260126-20260225"    # 最近30天
MIXED_90D="20251126-20260225"    # 最近90天
MIXED_180D="20250826-20260225"   # 最近180天
MIXED_365D="20250226-20260225"   # 最近365天 (完整一年)

# ==========================================
# 回测执行函数
# ==========================================

# 全局结果数组
typeset -a ALL_RESULTS

run_backtest() {
    local TIMERANGE=$1
    local LABEL=$2
    local TREND_TYPE=$3
    local LOG="$RESULTS_DIR/${STRATEGY}_${LABEL}.log"

    echo "  ⏳ 回测: $LABEL ($TIMERANGE) ..."
    
    if ! $FREQTRADE backtesting \
        --config "$CONFIG" \
        --strategy "$STRATEGY" \
        --strategy-path "$STRATEGY_PATH" \
        --timerange "$TIMERANGE" \
        --timeframe "$TIMEFRAME" \
        --data-format-ohlcv feather \
        --export none \
        > "$LOG" 2>&1; then
        echo "  ❌ 回测失败: $LABEL (查看 $LOG)"
        return 1
    fi

    # 提取关键指标 (从详细统计区域)
    local PROFIT=$(grep "│ Absolute profit" "$LOG" 2>/dev/null | awk -F'│' '{print $3}' | tr -d ' ')
    local PCTPROFIT=$(grep "│ Total profit %" "$LOG" 2>/dev/null | awk -F'│' '{print $3}' | tr -d ' ')
    local FACTOR=$(grep "│ Profit factor" "$LOG" 2>/dev/null | awk -F'│' '{print $3}' | tr -d ' ')
    local TRADES=$(grep "│ Total/Daily Avg" "$LOG" 2>/dev/null | awk -F'│' '{print $3}' | awk '{print $1}')
    local DD=$(grep "│ Max % of account" "$LOG" 2>/dev/null | awk -F'│' '{print $3}' | tr -d ' ')
    local SHARPE=$(grep "│ Sharpe" "$LOG" 2>/dev/null | awk -F'│' '{print $3}' | tr -d ' ')
    local SORTINO=$(grep "│ Sortino" "$LOG" 2>/dev/null | awk -F'│' '{print $3}' | tr -d ' ')
    
    # 从 STRATEGY SUMMARY 行提取胜率
    # 格式: │ Strategy │ Trades │ Avg% │ TotProfit │ Tot% │ Duration │ Win Draw Loss Win% │ Drawdown │ (空)
    # 字段索引: Win/Draw/Loss/Win% 在倒数第3个字段 (NF-2), Drawdown在NF-1, 空串在NF
    local WINRATE=$(grep "$STRATEGY" "$LOG" 2>/dev/null | grep "│" | tail -1 | awk -F'│' '{print $(NF-2)}' | awk '{print $NF}')
    
    # 设置默认值
    PCTPROFIT=${PCTPROFIT:-"N/A"}
    TRADES=${TRADES:-"0"}
    WINRATE=${WINRATE:-"N/A"}
    DD=${DD:-"N/A"}
    FACTOR=${FACTOR:-"N/A"}
    SHARPE=${SHARPE:-"N/A"}
    SORTINO=${SORTINO:-"N/A"}
    PROFIT=${PROFIT:-"N/A"}
    
    # 格式化输出
    printf "  ✅ %-20s | 收益%%: %-10s | 绝对收益: %-10s | 交易: %-5s | 胜率: %-8s | DD: %-8s | 因子: %-6s | Sharpe: %-6s | Sortino: %s\n" \
        "$LABEL" "$PCTPROFIT" "$PROFIT" "$TRADES" "$WINRATE" "$DD" "$FACTOR" "$SHARPE" "$SORTINO"
    
    # 保存结果到数组供后续汇总
    ALL_RESULTS+=("$TREND_TYPE,$LABEL,$TIMERANGE,$PCTPROFIT,$PROFIT,$TRADES,$WINRATE,$DD,$FACTOR,$SHARPE,$SORTINO")
}

# ==========================================
# 主测试流程
# ==========================================

echo ""
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║  VolatilitySystemV5 趋势稳定性全面测试                              ║"
echo "║  Advanced Market Microstructure Strategy Backtest                   ║"
echo "║  测试时间: $(date '+%Y-%m-%d %H:%M:%S')                              ║"
echo "║  数据范围: 2025-02-25 ~ 2026-02-25                                  ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"

# === 上行趋势测试 ===
echo ""
echo "┌──────────────────────────────────────────────────────────────────────┐"
echo "│  📈 上行趋势测试 (Bull Market) - 2025年4月~7月, BTC 82K → 115K     │"
echo "└──────────────────────────────────────────────────────────────────────┘"
run_backtest "$BULL_7D"  "上行-7天"  "上行"
run_backtest "$BULL_14D" "上行-14天" "上行"
run_backtest "$BULL_30D" "上行-30天" "上行"
run_backtest "$BULL_90D" "上行-90天" "上行"

# === 震荡趋势测试 ===
echo ""
echo "┌──────────────────────────────────────────────────────────────────────┐"
echo "│  📊 震荡趋势测试 (Range Market) - 2025年9~11月/12月~2026年1月       │"
echo "└──────────────────────────────────────────────────────────────────────┘"
run_backtest "$RANGE_7D"  "震荡-7天"  "震荡"
run_backtest "$RANGE_14D" "震荡-14天" "震荡"
run_backtest "$RANGE_30D" "震荡-30天" "震荡"
run_backtest "$RANGE_90D" "震荡-90天" "震荡"

# === 下行趋势测试 ===
echo ""
echo "┌──────────────────────────────────────────────────────────────────────┐"
echo "│  📉 下行趋势测试 (Bear Market) - 2025年10~12月, BTC 113K → 83K     │"
echo "└──────────────────────────────────────────────────────────────────────┘"
run_backtest "$BEAR_7D"  "下行-7天"  "下行"
run_backtest "$BEAR_14D" "下行-14天" "下行"
run_backtest "$BEAR_30D" "下行-30天" "下行"
run_backtest "$BEAR_90D" "下行-90天" "下行"

# === 混合周期测试 ===
echo ""
echo "┌──────────────────────────────────────────────────────────────────────┐"
echo "│  🔄 混合周期测试 (Mixed Market) - 包含多种市场环境                   │"
echo "└──────────────────────────────────────────────────────────────────────┘"
run_backtest "$MIXED_30D"  "混合-30天"  "混合"
run_backtest "$MIXED_90D"  "混合-90天"  "混合"
run_backtest "$MIXED_180D" "混合-180天" "混合"
run_backtest "$MIXED_365D" "混合-365天" "混合"

# ==========================================
# 生成汇总CSV
# ==========================================

SUMMARY_FILE="$RESULTS_DIR/summary_$(date '+%Y%m%d_%H%M%S').csv"
echo "趋势类型,标签,时间范围,收益率%,绝对收益,交易次数,胜率,最大回撤,盈亏因子,Sharpe,Sortino" > "$SUMMARY_FILE"

for result in "${ALL_RESULTS[@]}"; do
    echo "$result" >> "$SUMMARY_FILE"
done

# ==========================================
# 生成Markdown分析报告
# ==========================================

REPORT_FILE="$RESULTS_DIR/V5_TREND_ANALYSIS_$(date '+%Y%m%d_%H%M%S').md"

cat > "$REPORT_FILE" << 'REPORT_HEADER'
# VolatilitySystemV5 趋势稳定性分析报告

## 策略简介

**VolatilitySystemV5** 是一个基于市场微结构的高级合约交易策略，核心特性包括：

1. **波动率聚类检测**: 避免在极端波动飙升期间入场
2. **成交量分析**: 用成交量确认趋势强度
3. **RSI动态过滤**: 在震荡市中防止在极端位置入场
4. **自适应止损**: 震荡市收紧止损，趋势市放宽止损
5. **动态杠杆**: 基于波动率和市场状态调整杠杆倍数

## 测试结果

REPORT_HEADER

# 添加测试结果表格
echo "### 各时段表现汇总" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "| 趋势类型 | 标签 | 时间范围 | 收益率% | 绝对收益 | 交易数 | 胜率 | 最大回撤 | 盈亏因子 | Sharpe | Sortino |" >> "$REPORT_FILE"
echo "|----------|------|----------|---------|----------|--------|------|----------|----------|--------|---------|" >> "$REPORT_FILE"

for result in "${ALL_RESULTS[@]}"; do
    IFS=',' read -r trend label timerange pctprofit profit trades winrate dd factor sharpe sortino <<< "$result"
    echo "| $trend | $label | $timerange | $pctprofit | $profit | $trades | $winrate | $dd | $factor | $sharpe | $sortino |" >> "$REPORT_FILE"
done

cat >> "$REPORT_FILE" << 'REPORT_FOOTER'

## 分析维度

### 1. 趋势适应性
- **牛市表现**: 策略能否在上涨趋势中捕获足够利润
- **熊市表现**: 做空能力是否有效，下跌保护机制如何
- **震荡市表现**: 过滤噪音交易的能力

### 2. 时间稳定性
- **短期(7-14天)**: 策略在短期波动中的表现
- **中期(30天)**: 策略在一个完整月度周期中的稳定性
- **长期(90-365天)**: 策略的长期盈利能力和一致性

### 3. 关键指标评估
- **收益率**: 各时段的绝对和百分比收益
- **最大回撤**: 风险控制能力
- **盈亏因子**: 每1元亏损能赚多少（>1.5为优秀）
- **Sharpe比率**: 风险调整后收益（>1.0为良好）
- **Sortino比率**: 下行风险调整后收益（>1.5为优秀）

### 4. 改进建议
- 若牛市收益低于市场涨幅 → 考虑提高趋势市杠杆或放松入场条件
- 若震荡市亏损较大 → 收紧震荡市过滤条件或减小仓位
- 若熊市做空收益不佳 → 优化做空入场逻辑和止损位置
- 若短期波动大但长期稳定 → 策略整体合理，注意仓位管理

---
*报告生成时间: $(date '+%Y-%m-%d %H:%M:%S')*
*策略版本: VolatilitySystemV5*
*数据源: Gate.io Futures (BTC, ETH, SOL, ADA, XRP, DOGE, DOT, AVAX, LTC, LINK)*
REPORT_FOOTER

# ==========================================
# 最终输出
# ==========================================

echo ""
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║  测试完成！                                                         ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""
echo "📁 详细日志目录: $RESULTS_DIR/"
echo "📊 汇总CSV文件:  $SUMMARY_FILE"
echo "📄 分析报告:     $REPORT_FILE"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 后续分析建议："
echo "  1. 比较不同趋势下的胜率和盈亏比 → 评估策略方向性偏好"
echo "  2. 分析回撤在各种市场环境下的控制情况 → 评估风险管理"
echo "  3. 评估策略在震荡市中的表现 → 验证过滤机制效果"
echo "  4. 观察长周期（90天+）的稳定性 → 评估长期可用性"
echo "  5. 对比短期/长期Sharpe比率 → 判断策略是否随时间衰减"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""