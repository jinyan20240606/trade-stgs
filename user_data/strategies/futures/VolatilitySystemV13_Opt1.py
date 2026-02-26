# flake8: noqa: F401
# isort: skip_file
# --- Do not remove these libs ---
from datetime import datetime
from typing import Optional

import numpy as np  # noqa
import pandas as pd  # noqa
from pandas import DataFrame

import talib.abstract as ta
from freqtrade.persistence import Trade
from freqtrade.strategy import (CategoricalParameter, DecimalParameter,
                                IntParameter, IStrategy)
from freqtrade.exchange import date_minus_candles
import freqtrade.vendor.qtpylib.indicators as qtpylib

from technical.util import resample_to_interval, resampled_merge


class VolatilitySystemV13_Opt1(IStrategy):
    """
    V13-Opt1: 加仓质量控制 — adjust_trade_position 中也要求 MACD 夹角 < 100°
    
    基准: V11-Opt2 (41.71%, Sharpe 2.00, MaxDD 4.59%)
    
    核心思路:
    - V11-Opt2 已在「首次入场」时过滤低质量信号（MACD波峰夹角<100°）
    - 但 adjust_trade_position（加仓）完全不考虑 MACD 夹角
    - 加仓时若 MACD 动量正在减弱（夹角>100°），可能在不良时机加重仓位
    - 本版本：加仓也要求 MACD 夹角 < 100°
    
    变化:
    - 入场逻辑: 与 V11-Opt2 完全一致
    - 出场逻辑: 与 V11-Opt2/V7-E 完全一致
    - 加仓条件: 新增 MACD 夹角 < 100° 过滤
    
    预期:
    - 减少低质量加仓，避免在动量减弱时加重亏损
    - 可能轻微减少总交易量（加仓次数降低）
    - 但每次加仓质量更高 → 期望值提升
    """
    can_short = True

    minimal_roi = {
        "0": 1.0,
        "2880": 0.50,
        "10080": 0.10
    }

    stoploss = -0.20
    trailing_stop = False
    timeframe = '1h'

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 3H 重采样（与 V7-E 一致）
        resample_int = 60 * 3
        resampled = resample_to_interval(dataframe, resample_int)
        resampled['atr'] = ta.ATR(resampled, timeperiod=14) * 2.0
        resampled['close_change'] = resampled['close'].diff()
        dataframe = resampled_merge(dataframe, resampled, fill_na=True)
        dataframe['atr'] = dataframe[f'resample_{resample_int}_atr']
        dataframe['close_change'] = dataframe[f'resample_{resample_int}_close_change']

        # 本地指标
        dataframe['atr_local'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)

        dataframe['ema_20'] = ta.EMA(dataframe, timeperiod=20)
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['ema_200'] = ta.EMA(dataframe, timeperiod=200)

        dataframe['volume_ma'] = ta.SMA(dataframe, timeperiod=20, price='volume')
        dataframe['vwap'] = qtpylib.rolling_vwap(dataframe, window=14)
        dataframe['high_volume'] = dataframe['volume'] > dataframe['volume_ma']

        dataframe['atr_std'] = dataframe['atr_local'].rolling(window=20).std()
        dataframe['atr_ma'] = dataframe['atr_local'].rolling(window=20).mean()
        dataframe['volatility_spike'] = dataframe['atr_local'] > (dataframe['atr_ma'] + 2 * dataframe['atr_std'])

        # 市场状态分类（与 V7-E 一致）
        dataframe['is_strong_trend'] = (
            (dataframe['adx'] > 25) &
            (dataframe['high_volume']) &
            (~dataframe['volatility_spike'])
        )
        dataframe['is_weak_trend'] = ((dataframe['adx'] > 20) & (dataframe['adx'] <= 25))
        dataframe['is_range'] = (dataframe['adx'] < 20)
        dataframe['is_very_strong_trend'] = (dataframe['adx'] > 30)

        # 动态ATR阈值（沿用 V7-E）
        dataframe['atr_multiplier'] = np.where(
            dataframe['volatility_spike'], 2.0,
            np.where(
                dataframe['is_strong_trend'], 0.8,
                np.where(
                    dataframe['is_weak_trend'], 1.0,
                    1.8
                )
            )
        )
        dataframe['dynamic_threshold'] = dataframe['atr'] * dataframe['atr_multiplier']

        # 趋势方向判定
        dataframe['trend_up'] = dataframe['close'] > dataframe['ema_50']
        dataframe['trend_down'] = dataframe['close'] < dataframe['ema_50']
        dataframe['major_trend_up'] = dataframe['close'] > dataframe['ema_200']
        dataframe['major_trend_down'] = dataframe['close'] < dataframe['ema_200']

        # ============================================================
        # MACD 柱状图及夹角特征计算（入场+加仓确认用）
        # ============================================================
        macd_result = ta.MACD(dataframe, fastperiod=12, slowperiod=26, signalperiod=9)
        dataframe['macd_hist'] = macd_result['macdhist']

        h0 = dataframe['macd_hist']
        h1 = dataframe['macd_hist'].shift(1)
        h2 = dataframe['macd_hist'].shift(2)

        # 局部波峰（正向动量峰）：前一根 hist > 0，且高于两侧
        peak = (h1 > 0) & (h1 > h2) & (h1 > h0)
        # 局部波谷（负向动量谷）：前一根 hist < 0，且低于两侧
        trough = (h1 < 0) & (h1 < h2) & (h1 < h0)

        dataframe['macd_peak'] = peak.astype(float)
        dataframe['macd_trough'] = trough.astype(float)

        def calc_peak_angle(hist_series, is_event_series):
            """计算相邻峰/谷连线绝对角度（度），前向填充"""
            angles = np.full(len(hist_series), np.nan)
            hist_arr = hist_series.values
            is_event = is_event_series.values.astype(bool)
            peak_times = []

            for i in range(len(hist_arr)):
                if is_event[i]:
                    peak_times.append((i, hist_arr[i]))
                    if len(peak_times) >= 2:
                        (i1, v1), (i2, v2) = peak_times[-2], peak_times[-1]
                        dt = i2 - i1
                        dv = v2 - v1
                        if dt > 0:
                            angles[i] = abs(np.degrees(np.arctan2(dv, dt)))

            # 前向填充：在非峰位置使用最近的角度值
            result = pd.Series(angles, index=hist_series.index)
            return result.ffill()

        dataframe['macd_peak_angle'] = calc_peak_angle(
            dataframe['macd_hist'], dataframe['macd_peak']
        )
        dataframe['macd_trough_angle'] = calc_peak_angle(
            dataframe['macd_hist'], dataframe['macd_trough']
        )

        # 入场确认：最近波峰/谷夹角 < 100°（动量加速形态）
        dataframe['macd_angle_long_ok'] = (
            dataframe['macd_peak_angle'] < 100
        ).fillna(False)

        dataframe['macd_angle_short_ok'] = (
            dataframe['macd_trough_angle'] < 100
        ).fillna(False)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """入场逻辑与 V11-Opt2 完全一致"""
        long_condition = (
            (dataframe['close_change'] * 1 > dataframe['dynamic_threshold'].shift(1)) &
            (
                (
                    (dataframe['is_strong_trend'] | dataframe['is_weak_trend']) &
                    dataframe['trend_up'] &
                    (dataframe['close'] > dataframe['vwap'])
                ) |
                (
                    dataframe['is_range'] &
                    (dataframe['rsi'] < 70)
                )
            ) &
            (~dataframe['volatility_spike'] | dataframe['high_volume']) &
            # MACD 柱状图夹角确认（仅入场过滤，不影响出场）
            dataframe['macd_angle_long_ok']
        )
        dataframe.loc[long_condition, 'enter_long'] = 1

        short_condition = (
            (dataframe['close_change'] * -1 > dataframe['dynamic_threshold'].shift(1)) &
            (
                (
                    (dataframe['is_strong_trend'] | dataframe['is_weak_trend']) &
                    dataframe['trend_down'] &
                    (dataframe['close'] < dataframe['vwap'])
                ) |
                (
                    dataframe['is_range'] &
                    (dataframe['rsi'] > 30)
                )
            ) &
            (~dataframe['volatility_spike'] | dataframe['high_volume']) &
            # MACD 柱状图夹角确认（仅入场过滤）
            dataframe['macd_angle_short_ok']
        )
        dataframe.loc[short_condition, 'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        出场完全沿用 V7-E：极强趋势(ADX>30)不出场
        不使用任何MACD辅助出场，避免截断趋势
        """
        dataframe.loc[
            (dataframe['enter_long'] == 1) &
            (
                dataframe['major_trend_up'] |
                dataframe['is_range']
            ) &
            (~dataframe['is_very_strong_trend']),
            'exit_short'] = 1

        dataframe.loc[
            (dataframe['enter_short'] == 1) &
            (
                dataframe['major_trend_down'] |
                dataframe['is_range']
            ) &
            (~dataframe['is_very_strong_trend']),
            'exit_long'] = 1

        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:
        """动态仓位（与 V7-B 一致）"""
        try:
            dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            if len(dataframe) > 0:
                last_candle = dataframe.iloc[-1]
                if last_candle['is_strong_trend']:
                    return proposed_stake * 0.7
                elif last_candle['is_range']:
                    return proposed_stake * 0.3
                else:
                    return proposed_stake * 0.5
        except Exception:
            pass
        return proposed_stake / 2

    position_adjustment_enable = True

    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                              current_rate: float, current_profit: float,
                              min_stake: Optional[float], max_stake: float,
                              current_entry_rate: float, current_exit_rate: float,
                              current_entry_profit: float, current_exit_profit: float,
                              **kwargs) -> Optional[float]:
        """
        V13-Opt1 核心改动: 加仓时额外要求 MACD 夹角 < 100°
        
        原 V11-Opt2: 只要有新信号且持仓<2次 就加仓
        本版本: 还额外要求 MACD 夹角确认，避免在动量减弱时加仓
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
        if len(dataframe) > 2:
            last_candle = dataframe.iloc[-1].squeeze()
            previous_candle = dataframe.iloc[-2].squeeze()
            signal_name = 'enter_long' if not trade.is_short else 'enter_short'
            prior_date = date_minus_candles(self.timeframe, 1, current_time)

            # 基本加仓条件（与 V11-Opt2 一致）
            basic_condition = (
                last_candle.get(signal_name, 0) == 1
                and previous_candle.get(signal_name, 0) != 1
                and trade.nr_of_successful_entries < 2
                and trade.orders and trade.orders[-1].order_date_utc < prior_date
            )

            if basic_condition:
                # V13-Opt1 新增：加仓时也检查 MACD 夹角
                if not trade.is_short:
                    # 多头加仓：要求波峰夹角 < 100°（动量仍在加速）
                    macd_angle_ok = last_candle.get('macd_angle_long_ok', False)
                else:
                    # 空头加仓：要求波谷夹角 < 100°
                    macd_angle_ok = last_candle.get('macd_angle_short_ok', False)

                if macd_angle_ok:
                    return trade.stake_amount

        return None

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, side: str,
                 **kwargs) -> float:
        """杠杆控制（与 V7-E 一致）"""
        leverage = 2.0
        try:
            dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            if len(dataframe) > 0:
                last_candle = dataframe.iloc[-1]
                atr_pct = last_candle['atr_local'] / last_candle['close']
                if atr_pct < 0.01:
                    base_leverage = 3.0
                elif atr_pct < 0.02:
                    base_leverage = 2.0
                else:
                    base_leverage = 1.0
                if last_candle['volatility_spike']:
                    leverage = max(base_leverage * 0.5, 1.0)
                elif last_candle['is_strong_trend']:
                    leverage = min(base_leverage * 1.5, 3.0)
                elif last_candle['is_range']:
                    leverage = max(base_leverage * 0.8, 1.0)
                else:
                    leverage = base_leverage
        except Exception:
            pass
        return min(leverage, max_leverage, 3.0)