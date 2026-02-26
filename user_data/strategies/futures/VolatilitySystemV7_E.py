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


class VolatilitySystemV7_E(IStrategy):
    """
    V7-E: 最佳组合 — V7-A(出场放宽) + V7-B(动态仓位)
    
    组合两个独立优化方向：
    1. V7-A的出场放宽：极强趋势(ADX>30)中不出场
    2. V7-B的动态仓位：强趋势70%仓位，震荡30%仓位
    
    两者互不干扰：A改出场信号，B改资金分配。
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
        resample_int = 60 * 3
        resampled = resample_to_interval(dataframe, resample_int)
        resampled['atr'] = ta.ATR(resampled, timeperiod=14) * 2.0
        resampled['close_change'] = resampled['close'].diff()
        dataframe = resampled_merge(dataframe, resampled, fill_na=True)
        dataframe['atr'] = dataframe[f'resample_{resample_int}_atr']
        dataframe['close_change'] = dataframe[f'resample_{resample_int}_close_change']
        
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
        
        dataframe['ema_slope'] = (dataframe['ema_20'] - dataframe['ema_20'].shift(5)) / dataframe['ema_20'].shift(5) * 100
        
        dataframe['is_strong_trend'] = (
            (dataframe['adx'] > 25) & 
            (dataframe['high_volume']) & 
            (~dataframe['volatility_spike'])
        )
        
        dataframe['is_weak_trend'] = (
            (dataframe['adx'] > 20) & 
            (dataframe['adx'] <= 25)
        )
        
        dataframe['is_range'] = (dataframe['adx'] < 20)
        
        # V7-A: 极强趋势检测
        dataframe['is_very_strong_trend'] = (dataframe['adx'] > 30)
        
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
        
        dataframe['trend_up'] = dataframe['close'] > dataframe['ema_50']
        dataframe['trend_down'] = dataframe['close'] < dataframe['ema_50']
        
        dataframe['major_trend_up'] = dataframe['close'] > dataframe['ema_200']
        dataframe['major_trend_down'] = dataframe['close'] < dataframe['ema_200']

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
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
            (
                ~dataframe['volatility_spike'] | dataframe['high_volume']
            )
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
            (
                ~dataframe['volatility_spike'] | dataframe['high_volume']
            )
        )
        dataframe.loc[short_condition, 'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        V7-A出场放宽: 极强趋势(ADX>30)中不出场
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
        """
        V7-B动态仓位: 强趋势70%, 弱趋势50%, 震荡30%
        """
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
        dataframe, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
        if len(dataframe) > 2:
            last_candle = dataframe.iloc[-1].squeeze()
            previous_candle = dataframe.iloc[-2].squeeze()
            signal_name = 'enter_long' if not trade.is_short else 'enter_short'
            prior_date = date_minus_candles(self.timeframe, 1, current_time)
            
            if (
                last_candle[signal_name] == 1
                and previous_candle[signal_name] != 1
                and trade.nr_of_successful_entries < 2
                and trade.orders[-1].order_date_utc < prior_date
            ):
                return trade.stake_amount
        return None
        
    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if len(dataframe) > 0:
            last_candle = dataframe.iloc[-1]
            if last_candle['is_range']:
                return -0.05
            if last_candle['is_strong_trend']:
                return -0.15
        return -0.10

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, side: str,
                 **kwargs) -> float:
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