#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
技術指標計算模組
包含 EMA5, RSI14, 量能比等 N字回撤掃描需要的技術指標
"""

import numpy as np
import pandas as pd
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class TechnicalIndicators:
    """技術指標計算器"""
    
    @staticmethod
    def ema(prices: pd.Series, period: int) -> pd.Series:
        """
        計算指數移動平均線 (EMA)
        
        Args:
            prices: 價格序列
            period: 週期
            
        Returns:
            EMA 序列
        """
        return prices.ewm(span=period, adjust=False).mean()
    
    @staticmethod
    def sma(prices: pd.Series, period: int) -> pd.Series:
        """
        計算簡單移動平均線 (SMA)
        
        Args:
            prices: 價格序列
            period: 週期
            
        Returns:
            SMA 序列
        """
        return prices.rolling(window=period).mean()
    
    @staticmethod
    def rsi_wilder(prices: pd.Series, period: int = 14) -> pd.Series:
        """
        計算 RSI (Wilder's smoothing method)
        
        Args:
            prices: 收盤價序列
            period: RSI 週期 (預設 14)
            
        Returns:
            RSI 序列 (0-100)
        """
        delta = prices.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        # Wilder's smoothing (與 EMA 相似但使用不同的 alpha)
        alpha = 1.0 / period
        avg_gain = gain.ewm(alpha=alpha, adjust=False).mean()
        avg_loss = loss.ewm(alpha=alpha, adjust=False).mean()
        
        # 避免除零
        rs = avg_gain / avg_loss.replace(0, np.inf)
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    @staticmethod
    def volume_ratio(volumes: pd.Series, period: int = 20) -> pd.Series:
        """
        計算量能比 (當日量 / N日平均量)
        
        Args:
            volumes: 成交量序列
            period: 平均量週期 (預設 20)
            
        Returns:
            量能比序列
        """
        avg_volume = volumes.rolling(window=period).mean()
        return volumes / avg_volume
    
    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """
        計算平均真實範圍 (ATR)
        
        Args:
            high: 最高價序列
            low: 最低價序列  
            close: 收盤價序列
            period: ATR 週期
            
        Returns:
            ATR 序列
        """
        prev_close = close.shift(1)
        
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.ewm(span=period, adjust=False).mean()
        
        return atr

class NPatternIndicators:
    """N字回撤專用指標計算"""
    
    def __init__(self, df: pd.DataFrame):
        """
        初始化指標計算器
        
        Args:
            df: DataFrame with columns ['date', 'open', 'high', 'low', 'close', 'volume']
        """
        self.df = df.copy()
        self.calc = TechnicalIndicators()
        self._calculate_all_indicators()
    
    def _calculate_all_indicators(self):
        """計算所有需要的技術指標"""
        # EMA5
        self.df['ema5'] = self.calc.ema(self.df['close'], 5)
        
        # EMA20 (用於多頭確認)
        self.df['ema20'] = self.calc.ema(self.df['close'], 20)
        
        # RSI14
        self.df['rsi14'] = self.calc.rsi_wilder(self.df['close'], 14)
        
        # 量能比 (20日)
        self.df['volume_ratio'] = self.calc.volume_ratio(self.df['volume'], 20)
        
        # 昨高 (用於突破確認)
        self.df['prev_high'] = self.df['high'].shift(1)
        
        # ATR (可選用於動態門檻)
        self.df['atr14'] = self.calc.atr(
            self.df['high'], 
            self.df['low'], 
            self.df['close'], 
            14
        )
    
    def get_latest_values(self) -> dict:
        """
        獲取最新一日的所有指標值
        
        Returns:
            dict with latest indicator values
        """
        if len(self.df) == 0:
            return {}
        
        latest = self.df.iloc[-1]
        
        return {
            'date': latest['date'],
            'close': latest['close'],
            'high': latest['high'],
            'low': latest['low'],
            'volume': latest['volume'],
            'ema5': latest['ema5'],
            'ema20': latest['ema20'],
            'rsi14': latest['rsi14'],
            'volume_ratio': latest['volume_ratio'],
            'prev_high': latest['prev_high'],
            'atr14': latest['atr14']
        }
    
    def check_trigger_conditions(self) -> dict:
        """
        檢查觸發條件 (三個條件任一成立)
        
        Returns:
            dict with trigger condition results
        """
        latest = self.get_latest_values()
        
        if not latest:
            return {'any_triggered': False}
        
        # 條件1：突破昨高
        condition1 = latest['close'] > latest['prev_high']
        
        # 條件2：量增上穿 EMA5
        condition2 = (latest['close'] > latest['ema5'] and 
                     latest['volume_ratio'] > 1.0)
        
        # 條件3：RSI 強勢
        condition3 = latest['rsi14'] >= 50
        
        return {
            'condition1_break_high': condition1,
            'condition2_volume_ema': condition2,  
            'condition3_rsi_strong': condition3,
            'any_triggered': condition1 or condition2 or condition3,
            'trigger_count': sum([condition1, condition2, condition3])
        }
    
    def calculate_pattern_score(self, A: dict, B: dict, C: dict) -> dict:
        """
        計算 N字形態的綜合評分
        
        Args:
            A, B, C: ABC 轉折點
            
        Returns:
            dict with detailed scoring breakdown
        """
        latest = self.get_latest_values()
        
        # 1. 回撤深度分 (40%)
        retr_pct = (B['price'] - C['price']) / (B['price'] - A['price'])
        retr_depth_score = 40 * (1 - 2 * abs(retr_pct - 0.5))
        
        # 2. 量能比分 (25%)
        vol_ratio = min(latest['volume_ratio'], 3.0) if latest.get('volume_ratio') else 1.0
        volume_score = 25 * (vol_ratio / 3.0)
        
        # 3. 反彈早期分 (15%) 
        bars_since_c = len(self.df) - C['index'] - 1
        early_score = 15 * max(0, (10 - bars_since_c) / 10)  # 10天內加分
        
        # 4. 均線多頭分 (10%)
        ma_score = 0
        if latest['close'] >= latest['ema5']:
            ma_score += 5
        if latest['close'] >= latest['ema20']:
            ma_score += 5
        
        # 5. 健康度分 (10%)
        health_score = 0
        rsi = latest.get('rsi14', 50)
        if 50 <= rsi <= 70:
            health_score += 10
        elif rsi > 75:
            health_score -= 5  # 過熱扣分
        elif rsi < 50:
            health_score -= 3  # 轉弱扣分
            
        # 單日漲幅檢查
        if len(self.df) >= 2:
            daily_change = (latest['close'] - self.df.iloc[-2]['close']) / self.df.iloc[-2]['close']
            if daily_change > 0.09:  # 超過9%單日漲幅
                health_score -= 5
        
        total_score = max(0, min(100, 
            retr_depth_score + volume_score + early_score + ma_score + health_score
        ))
        
        return {
            'total_score': round(total_score),
            'breakdown': {
                'retracement_depth': round(max(0, retr_depth_score), 1),
                'volume_ratio': round(max(0, volume_score), 1), 
                'early_entry': round(max(0, early_score), 1),
                'moving_average': round(max(0, ma_score), 1),
                'health_check': round(max(0, health_score), 1)
            },
            'metrics': {
                'retracement_pct': retr_pct,
                'volume_ratio': vol_ratio,
                'bars_since_c': bars_since_c,
                'rsi14': rsi
            }
        }
    
    def get_enriched_dataframe(self) -> pd.DataFrame:
        """返回包含所有指標的完整DataFrame"""
        return self.df.copy()

def test_indicators():
    """測試技術指標計算"""
    # 創建測試資料
    dates = pd.date_range('2024-01-01', periods=60, freq='D')
    np.random.seed(42)
    
    # 生成價格資料
    base_price = 100
    prices = [base_price]
    volumes = []
    
    for i in range(1, 60):
        # 價格隨機游走 + 趨勢
        change = np.random.normal(0, 0.02) + 0.001  # 輕微上漲趨勢
        new_price = prices[-1] * (1 + change)
        prices.append(new_price)
        
        # 成交量
        vol = np.random.uniform(1000000, 5000000)
        volumes.append(vol)
    
    # 創建OHLC
    df = pd.DataFrame({
        'date': dates,
        'open': [p * np.random.uniform(0.995, 1.005) for p in prices],
        'high': [p * np.random.uniform(1.005, 1.02) for p in prices],
        'low': [p * np.random.uniform(0.98, 0.995) for p in prices], 
        'close': prices,
        'volume': [1000000] + volumes
    })
    
    # 測試指標計算
    indicators = NPatternIndicators(df)
    latest = indicators.get_latest_values()
    
    print("最新指標值:")
    print(f"  收盤價: {latest['close']:.2f}")
    print(f"  EMA5: {latest['ema5']:.2f}")
    print(f"  EMA20: {latest['ema20']:.2f}")
    print(f"  RSI14: {latest['rsi14']:.1f}")
    print(f"  量能比: {latest['volume_ratio']:.2f}")
    
    # 測試觸發條件
    triggers = indicators.check_trigger_conditions()
    print(f"\n觸發條件檢查:")
    print(f"  突破昨高: {triggers['condition1_break_high']}")
    print(f"  量增上穿EMA5: {triggers['condition2_volume_ema']}")
    print(f"  RSI強勢: {triggers['condition3_rsi_strong']}")
    print(f"  任一觸發: {triggers['any_triggered']}")

if __name__ == "__main__":
    test_indicators()