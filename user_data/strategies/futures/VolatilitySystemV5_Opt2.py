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


class VolatilitySystemV5_Opt2(IStrategy):
    """
    Volatility System V5 - Optimization 2: Short Position Exit Optimization
    
    Changes vs V5:
    1. Exit logic now uses EMA200 as a major trend filter:
       - Exit long requires: reverse signal AND price below EMA200 (confirms downtrend)
       - Exit short requires: reverse signal AND price above EMA200 (confirms uptrend)
       - This prevents premature exits during temporary pullbacks within a strong trend
    2. In clear downtrend (price < EMA200), short exits are more reluctant
    3. In clear uptrend (price > EMA200), long exits are more reluctant
    """
    can_short = True

    # ROI: Almost disabled to let trend run
    minimal_roi = {
        "0": 1.0,       # 100% profit
        "2880": 0.50,   # 50% after 48 hours
        "10080": 0.10   # 10% after 1 week
    }

    # Stoploss: Dynamic, but set a safety net
    stoploss = -0.20

    # Trailing stop: Disabled to capture full trend
    trailing_stop = False

    # Optimal ticker interval for the strategy
    timeframe = '1h'

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Advanced indicators including Volume and Volatility Clustering
        """
        resample_int = 60 * 3
        resampled = resample_to_interval(dataframe, resample_int)
        
        # Average True Range (ATR)
        resampled['atr'] = ta.ATR(resampled, timeperiod=14) * 2.0
        # Absolute close change
        resampled['close_change'] = resampled['close'].diff()

        dataframe = resampled_merge(dataframe, resampled, fill_na=True)
        dataframe['atr'] = dataframe[f'resample_{resample_int}_atr']
        dataframe['close_change'] = dataframe[f'resample_{resample_int}_close_change']
        
        # === 1. Basic Trend Indicators ===
        dataframe['atr_local'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        # EMAs
        dataframe['ema_20'] = ta.EMA(dataframe, timeperiod=20)
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['ema_200'] = ta.EMA(dataframe, timeperiod=200)
        
        # === 2. Volume Analysis ===
        # Volume MA
        dataframe['volume_ma'] = ta.SMA(dataframe, timeperiod=20, price='volume')
        
        # VWAP (Approximation)
        dataframe['vwap'] = qtpylib.rolling_vwap(dataframe, window=14)
        
        # Volume Trend Confirmation
        # High volume supports the trend
        dataframe['high_volume'] = dataframe['volume'] > dataframe['volume_ma']
        
        # === 3. Volatility Clustering ===
        # Calculate standard deviation of ATR to detect volatility spikes
        dataframe['atr_std'] = dataframe['atr_local'].rolling(window=20).std()
        dataframe['atr_ma'] = dataframe['atr_local'].rolling(window=20).mean()
        
        # Volatility Spike: ATR is 2 standard deviations above mean
        dataframe['volatility_spike'] = dataframe['atr_local'] > (dataframe['atr_ma'] + 2 * dataframe['atr_std'])
        
        # === 4. Market State Classification ===
        
        # Trend slope
        dataframe['ema_slope'] = (dataframe['ema_20'] - dataframe['ema_20'].shift(5)) / dataframe['ema_20'].shift(5) * 100
        
        # Strong Trend: High ADX + Volume Support + No Extreme Volatility
        dataframe['is_strong_trend'] = (
            (dataframe['adx'] > 25) & 
            (dataframe['high_volume']) & 
            (~dataframe['volatility_spike'])
        )
        
        # Weak Trend: Moderate ADX
        dataframe['is_weak_trend'] = (
            (dataframe['adx'] > 20) & 
            (dataframe['adx'] <= 25)
        )
        
        # Range: Low ADX
        dataframe['is_range'] = (dataframe['adx'] < 20)
        
        # === 5. Dynamic Parameters ===
        
        # ATR Multiplier
        dataframe['atr_multiplier'] = np.where(
            dataframe['volatility_spike'], 2.0,
            np.where(
                dataframe['is_strong_trend'], 0.8,
                np.where(
                    dataframe['is_weak_trend'], 1.0,
                    1.8  # Range market
                )
            )
        )
        
        # Dynamic Threshold
        dataframe['dynamic_threshold'] = dataframe['atr'] * dataframe['atr_multiplier']
        
        # Trend Direction
        dataframe['trend_up'] = dataframe['close'] > dataframe['ema_50']
        dataframe['trend_down'] = dataframe['close'] < dataframe['ema_50']
        
        # === OPT2: Major Trend Direction (EMA200) ===
        dataframe['major_trend_up'] = dataframe['close'] > dataframe['ema_200']
        dataframe['major_trend_down'] = dataframe['close'] < dataframe['ema_200']

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Entry logic with Volume and RSI filters (same as V5)
        """
        # === Long Entry ===
        long_condition = (
            # 1. Price breakout
            (dataframe['close_change'] * 1 > dataframe['dynamic_threshold'].shift(1)) &
            
            # 2. Trend Filter
            (
                # Strong/Weak Trend: Must be above EMA50 and VWAP
                (
                    (dataframe['is_strong_trend'] | dataframe['is_weak_trend']) & 
                    dataframe['trend_up'] & 
                    (dataframe['close'] > dataframe['vwap'])
                ) |
                # Range: RSI must not be overbought (>70)
                (
                    dataframe['is_range'] & 
                    (dataframe['rsi'] < 70)
                )
            ) &
            
            # 3. Volatility Safety (Avoid entry during extreme spikes unless strong volume)
            (
                ~dataframe['volatility_spike'] | dataframe['high_volume']
            )
        )
        
        dataframe.loc[long_condition, 'enter_long'] = 1
        
        # === Short Entry ===
        short_condition = (
            # 1. Price breakout
            (dataframe['close_change'] * -1 > dataframe['dynamic_threshold'].shift(1)) &
            
            # 2. Trend Filter
            (
                # Strong/Weak Trend: Must be below EMA50 and VWAP
                (
                    (dataframe['is_strong_trend'] | dataframe['is_weak_trend']) & 
                    dataframe['trend_down'] & 
                    (dataframe['close'] < dataframe['vwap'])
                ) |
                # Range: RSI must not be oversold (<30)
                (
                    dataframe['is_range'] & 
                    (dataframe['rsi'] > 30)
                )
            ) &
            
            # 3. Volatility Safety
            (
                ~dataframe['volatility_spike'] | dataframe['high_volume']
            )
        )
        
        dataframe.loc[short_condition, 'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        OPT2: Exit with EMA200 major trend confirmation
        
        Key change: Don't exit a position just because there's a reverse signal.
        Also require the major trend (EMA200) to confirm the reversal.
        
        - Exit long: need short signal AND (price < EMA200 OR in range market)
        - Exit short: need long signal AND (price > EMA200 OR in range market)
        
        In range markets (ADX < 20), we still allow normal exits to avoid holding 
        unprofitable positions in choppy conditions.
        """
        # Exit short: when long signal fires AND major trend confirms uptrend
        dataframe.loc[
            (dataframe['enter_long'] == 1) & 
            (
                dataframe['major_trend_up'] |  # Price above EMA200 = uptrend confirmed
                dataframe['is_range']          # In range, allow exit to avoid chop
            ),
            'exit_short'] = 1
        
        # Exit long: when short signal fires AND major trend confirms downtrend
        dataframe.loc[
            (dataframe['enter_short'] == 1) & 
            (
                dataframe['major_trend_down'] |  # Price below EMA200 = downtrend confirmed
                dataframe['is_range']             # In range, allow exit to avoid chop
            ),
            'exit_long'] = 1
            
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:
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
        """
        Adaptive Stoploss based on market volatility
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if len(dataframe) > 0:
            last_candle = dataframe.iloc[-1]
            
            # In range markets, use tighter stoploss
            if last_candle['is_range']:
                return -0.05  # 5% stop in range
            
            # In strong trends, give more room
            if last_candle['is_strong_trend']:
                return -0.15  # 15% stop in strong trend
                
        # Default fallback
        return -0.10

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, side: str,
                 **kwargs) -> float:
        """
        Risk-Based Leverage
        """
        leverage = 2.0
        try:
            dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            if len(dataframe) > 0:
                last_candle = dataframe.iloc[-1]
                
                # 1. Base leverage on volatility (ATR %)
                atr_pct = last_candle['atr_local'] / last_candle['close']
                
                if atr_pct < 0.01:
                    base_leverage = 3.0
                elif atr_pct < 0.02:
                    base_leverage = 2.0
                else:
                    base_leverage = 1.0
                
                # 2. Adjust for Volatility Spike (Risk Reduction)
                if last_candle['volatility_spike']:
                    # Cut leverage in half during volatility spikes
                    leverage = max(base_leverage * 0.5, 1.0)
                
                # 3. Adjust for Strong Trend (Opportunity)
                elif last_candle['is_strong_trend']:
                    leverage = min(base_leverage * 1.5, 3.0)
                
                # 4. Range Market
                elif last_candle['is_range']:
                    leverage = max(base_leverage * 0.8, 1.0)
                else:
                    leverage = base_leverage
                    
        except Exception:
            pass
        return min(leverage, max_leverage, 3.0)