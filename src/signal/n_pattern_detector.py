#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
N字回撤偵測器 - 核心演算法模組
"""

import pandas as pd
import numpy as np
from typing import Optional, Tuple, Dict, List, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class NPatternSignal:
    """N字回撤訊號數據結構"""
    stock_id: str
    signal_date: str
    
    # ABC 關鍵點
    A_price: float
    A_date: str
    B_price: float
    B_date: str
    C_price: float
    C_date: str
    
    # 形態參數
    rise_pct: float          # A到B漲幅比例
    retr_pct: float          # B到C回撤比例
    bars_ab: int             # A到B的交易日數
    bars_bc: int             # B到C的交易日數
    bars_c_to_signal: int    # C到訊號日的交易日數
    
    # 例外狀態記錄
    ab_is_exception: bool    # AB段是否通過例外條件
    bc_is_exception: bool    # BC段是否通過例外條件
    
    # 技術指標
    ema5: float
    ema20: float
    rsi14: float
    volume_ratio: float      # 當日量能比(vs 20日均量)
    
    # 觸發條件
    trigger_break_yesterday_high: bool
    trigger_ema5_volume: bool
    trigger_rsi_strong: bool
    
    # 評分
    score: int
    score_breakdown: Dict[str, float]

class ZigZagDetector:
    """ZigZag 切腳偵測器"""
    
    def __init__(self, min_change_pct: float = 0.015):
        """
        Args:
            min_change_pct: 最小變化百分比 (預設1.5%)
        """
        self.min_change_pct = min_change_pct
    
    def detect(self, df: pd.DataFrame) -> List[Tuple[int, float, str]]:
        """
        偵測 ZigZag 轉折點 - 全新算法，避免卡住問題
        
        Args:
            df: 包含 date, high, low, close 的 DataFrame
            
        Returns:
            List of (index, price, type) where type is 'H' or 'L'
        """
        if len(df) < 3:
            return []
        
        points = []
        
        # 從第一根K線開始，以低點作為起始樞紐
        points.append((0, df.iloc[0]['low'], 'L'))
        
        direction = 'up'  # 'up' 表示在尋找高點, 'down' 表示在尋找低點
        extreme_idx = 0
        extreme_price = df.iloc[0]['low']
        
        for i in range(1, len(df)):
            if direction == 'up':
                # 正在尋找高點
                current_high = df.iloc[i]['high']
                
                # 更新極值候選
                if current_high > extreme_price:
                    extreme_idx = i
                    extreme_price = current_high
                
                # 檢查是否應該確認高點並轉為尋找低點
                # 計算相對於最後確認的低點的變化
                last_low_price = points[-1][1]  # 最後一個轉折點的價格
                rise_pct = (extreme_price - last_low_price) / last_low_price
                
                # 如果當前價格相對於極值點的跌幅達到閾值，確認極值為高點
                current_low = df.iloc[i]['low']
                if extreme_price > 0:  # 避免除零
                    decline_from_extreme = (extreme_price - current_low) / extreme_price
                    
                    if decline_from_extreme >= self.min_change_pct and rise_pct >= self.min_change_pct:
                        # 確認高點
                        points.append((extreme_idx, extreme_price, 'H'))
                        direction = 'down'
                        extreme_idx = i
                        extreme_price = current_low
                        
            else:  # direction == 'down'
                # 正在尋找低點
                current_low = df.iloc[i]['low']
                
                # 更新極值候選
                if current_low < extreme_price:
                    extreme_idx = i
                    extreme_price = current_low
                
                # 檢查是否應該確認低點並轉為尋找高點
                # 計算相對於最後確認的高點的變化
                last_high_price = points[-1][1]  # 最後一個轉折點的價格
                decline_pct = (last_high_price - extreme_price) / last_high_price
                
                # 如果當前價格相對於極值點的漲幅達到閾值，確認極值為低點
                current_high = df.iloc[i]['high']
                if extreme_price > 0:  # 避免除零
                    rise_from_extreme = (current_high - extreme_price) / extreme_price
                    
                    if rise_from_extreme >= self.min_change_pct and decline_pct >= self.min_change_pct:
                        # 確認低點
                        points.append((extreme_idx, extreme_price, 'L'))
                        direction = 'up'
                        extreme_idx = i
                        extreme_price = current_high
        
        # 收尾：添加最後的極值（如果有意義的話）
        if len(points) > 0 and extreme_idx > points[-1][0]:
            # 檢查最後的極值是否有足夠的變化幅度
            last_point_price = points[-1][1]
            
            if direction == 'up' and extreme_price > 0:
                # 最後在尋找高點
                change_pct = (extreme_price - last_point_price) / last_point_price
                if change_pct >= self.min_change_pct:
                    points.append((extreme_idx, extreme_price, 'H'))
            elif direction == 'down' and last_point_price > 0:
                # 最後在尋找低點  
                change_pct = (last_point_price - extreme_price) / last_point_price
                if change_pct >= self.min_change_pct:
                    points.append((extreme_idx, extreme_price, 'L'))
        
        return points

class TechnicalIndicators:
    """技術指標計算器"""
    
    @staticmethod
    def ema(series: pd.Series, period: int) -> pd.Series:
        """計算指數移動平均"""
        return series.ewm(span=period, adjust=False).mean()
    
    @staticmethod
    def sma(series: pd.Series, period: int) -> pd.Series:
        """計算簡單移動平均"""
        return series.rolling(window=period).mean()
    
    @staticmethod
    def rsi_wilder(close: pd.Series, period: int = 14) -> pd.Series:
        """計算 RSI (Wilder 方法)"""
        delta = close.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        # 初始值用簡單平均
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        
        # Wilder 平滑
        alpha = 1.0 / period
        for i in range(period, len(gain)):
            avg_gain.iloc[i] = alpha * gain.iloc[i] + (1 - alpha) * avg_gain.iloc[i-1]
            avg_loss.iloc[i] = alpha * loss.iloc[i] + (1 - alpha) * avg_loss.iloc[i-1]
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    @staticmethod
    def volume_ratio(volume: pd.Series, period: int = 20) -> pd.Series:
        """計算量能比 (當日量 / 過去N日平均量，不含當日)"""
        # 不含當日的過去N日平均量
        avg_volume = volume.rolling(window=period, min_periods=10).mean().shift(1)
        
        # 清理異常值
        volume_clean = volume.replace(0, np.nan)
        avg_volume_clean = avg_volume.replace(0, np.nan)
        
        ratio = volume_clean / avg_volume_clean
        # 上限截斷到10，避免極端值
        return ratio.clip(upper=10)
    
    @staticmethod
    def atr_wilder(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """計算ATR使用Wilder方法"""
        # 計算True Range
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = abs(high - prev_close)
        tr3 = abs(low - prev_close)
        
        # 取最大值
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # 初始值用前14根的簡單平均
        atr = true_range.rolling(window=period).mean()
        
        # Wilder平滑
        alpha = 1.0 / period
        for i in range(period, len(true_range)):
            atr.iloc[i] = alpha * true_range.iloc[i] + (1 - alpha) * atr.iloc[i-1]
        
        return atr
    
    @staticmethod
    def dynamic_zigzag_threshold(close: pd.Series, high: pd.Series, low: pd.Series, 
                                period: int = 14, smooth_period: int = 5,
                                atr_multiplier: float = 0.8, floor: float = 0.02, cap: float = 0.05) -> pd.Series:
        """計算動態ZigZag門檻"""
        atr = TechnicalIndicators.atr_wilder(high, low, close, period)
        atr_pct = atr / close
        
        # 平滑
        atr_smooth = atr_pct.rolling(window=smooth_period, min_periods=1).mean()
        
        # 動態門檻: atr_multiplier * atr_smooth，限制在floor-cap之間
        threshold = (atr_multiplier * atr_smooth).clip(lower=floor, upper=cap)
        return threshold

class NPatternDetector:
    """N字回撤偵測器主類"""
    
    def __init__(self, 
                 lookback_bars: int = 60,
                 use_dynamic_zigzag: bool = True,   # 使用動態ZigZag門檻
                 zigzag_change_pct: float = 0.025,  # 固定門檻(備用)
                 # 動態ZigZag參數
                 atr_len: int = 14,                 # ATR計算期間
                 atr_smooth: int = 5,               # ATR平滑期間
                 atr_multiplier: float = 0.8,       # ATR倍數
                 zigzag_floor: float = 0.02,        # 動態門檻下限
                 zigzag_cap: float = 0.05,          # 動態門檻上限
                 # 波段與回撤參數
                 min_leg_pct: float = 0.06,         # 6%最小波段
                 retr_min: float = 0.20,
                 retr_max: float = 0.80,
                 c_tolerance: float = 0.00,
                 # 時間護欄參數
                 min_bars_ab: int = 3,              # AB段最少3天
                 max_bars_ab: int = 30,             # AB段最多30天
                 min_bars_bc: int = 3,              # BC段最少3天
                 max_bars_bc: int = 15,             # BC段最多15天
                 max_bars_from_c: int = 12,         # C到今天最多12天
                 # 技術指標參數
                 volume_threshold: float = 1.0,     # 量能門檻
                 ema_len: int = 5,
                 ema20_len: int = 20,
                 rsi_len: int = 14,
                 vol_ma_len: int = 20):
        """
        Args:
            lookback_bars: 回看交易日數
            use_dynamic_zigzag: 是否使用動態ZigZag門檻
            zigzag_change_pct: 固定ZigZag門檻(當不使用動態時)
            min_leg_pct: 最小波段漲幅
            retr_min: 最小回撤比例
            retr_max: 最大回撤比例
            c_tolerance: C點可低於A點的容忍度
            min_bars_ab: AB段最小天數(要求足夠的走勢時間)
            max_bars_ab: AB段最大天數(避免變盤整)
            min_bars_bc: BC段最小天數(要求足夠的整理時間)
            max_bars_bc: BC段最大天數(避免回撤過久)
            max_bars_from_c: C點到今天的最大天數(新鮮度)
            volume_threshold: 量增觸發門檻
            ema_len: EMA短期長度
            ema20_len: EMA長期長度
            rsi_len: RSI計算期間
            vol_ma_len: 量能平均期間
        """
        # 基本參數
        self.lookback_bars = lookback_bars
        self.use_dynamic_zigzag = use_dynamic_zigzag
        self.zigzag_change_pct = zigzag_change_pct
        # 動態ZigZag參數
        self.atr_len = atr_len
        self.atr_smooth = atr_smooth
        self.atr_multiplier = atr_multiplier
        self.zigzag_floor = zigzag_floor
        self.zigzag_cap = zigzag_cap
        # 波段與回撤參數
        self.min_leg_pct = min_leg_pct
        self.retr_min = retr_min
        self.retr_max = retr_max
        self.c_tolerance = c_tolerance
        # 時間護欄參數
        self.min_bars_ab = min_bars_ab
        self.max_bars_ab = max_bars_ab
        self.min_bars_bc = min_bars_bc
        self.max_bars_bc = max_bars_bc
        self.max_bars_from_c = max_bars_from_c
        # 技術指標參數
        self.volume_threshold = volume_threshold
        self.ema_len = ema_len
        self.ema20_len = ema20_len
        self.rsi_len = rsi_len
        self.vol_ma_len = vol_ma_len
        
        self.zigzag = ZigZagDetector(min_change_pct=zigzag_change_pct)
        self.indicators = TechnicalIndicators()
    
    def find_last_abc_pattern(self, zigzag_points: List[Tuple[int, float, str]], 
                             df: pd.DataFrame) -> Optional[Tuple[int, int, int]]:
        """
        在 ZigZag 點中尋找最後一個符合條件的 ABC 形態
        
        Returns:
            (A_idx, B_idx, C_idx) or None
        """
        if len(zigzag_points) < 3:
            return None
        
        # 從最後往前找 L-H-L 形態
        for i in range(len(zigzag_points) - 1, 1, -1):
            if i < 2:
                break
                
            # 檢查 L-H-L 模式
            C_idx, C_price, C_type = zigzag_points[i]
            B_idx, B_price, B_type = zigzag_points[i-1]
            A_idx, A_price, A_type = zigzag_points[i-2]
            
            if A_type != 'L' or B_type != 'H' or C_type != 'L':
                continue
            
            # 檢查 N 字形態條件
            # 1. A到B的漲幅足夠 (除零保護)
            eps = 1e-9
            rise_pct = (B_price - A_price) / max(A_price, eps)
            if rise_pct < self.min_leg_pct:
                continue
            
            # 2. B到C的回撤比例在合理範圍 (除零保護)
            retr_base = max(B_price - A_price, eps)
            retr_pct = (B_price - C_price) / retr_base
            if retr_pct < self.retr_min or retr_pct > self.retr_max:
                continue
            
            # 3. C點不能明顯低於A點
            if C_price < A_price * (1 - self.c_tolerance):
                continue
            
            # 4. 時間護欄檢查(含例外條件)
            bars_ab = B_idx - A_idx
            bars_bc = C_idx - B_idx
            bars_from_c = len(df) - 1 - C_idx
            
            # AB段時間檢查(含高速行情例外)
            ab_pass = False
            ab_is_exception = False
            if bars_ab >= self.min_bars_ab and bars_ab <= self.max_bars_ab:
                # 標準情況通過
                ab_pass = True
            elif bars_ab < self.min_bars_ab:
                # 例外條件：AB段1-2根也放行，但需嚴格條件
                # 計算ATR比例作為動態門檻
                atr14 = TechnicalIndicators.atr_wilder(df['high'], df['low'], df['close'], self.atr_len)
                if not atr14.isna().iloc[B_idx]:  # 確保ATR有效
                    close_at_b = df.iloc[B_idx]['close']
                    atr_pct = atr14.iloc[B_idx] / max(close_at_b, 1e-9)
                    required_rise = max(self.min_leg_pct, 1.8 * atr_pct)
                    
                    # 修正: 使用B當天的量比 (確認索引)
                    vol_ratio_series = TechnicalIndicators.volume_ratio(df['volume'], self.vol_ma_len)
                    if not vol_ratio_series.isna().iloc[B_idx]:
                        current_vol_ratio = float(vol_ratio_series.iloc[B_idx])
                    else:
                        current_vol_ratio = 1.0
                    
                    if rise_pct >= required_rise and current_vol_ratio >= 1.5:
                        ab_pass = True
                        ab_is_exception = True
            
            if not ab_pass:
                continue
            
            # BC段時間檢查(含例外條件)
            bc_pass = False
            bc_is_exception = False
            if bars_bc >= self.min_bars_bc and bars_bc <= self.max_bars_bc:
                # 標準情況通過
                bc_pass = True
            elif bars_bc == 2:  # 只允許2根的例外
                # 檢查回撤比例是否在合理範圍
                if 0.30 <= retr_pct <= 0.70:
                    # 修正: 使用C當天的量比 (確認索引)
                    vol_ratio_series = TechnicalIndicators.volume_ratio(df['volume'], self.vol_ma_len)
                    if not vol_ratio_series.isna().iloc[C_idx]:
                        current_vol_ratio = float(vol_ratio_series.iloc[C_idx])
                    else:
                        current_vol_ratio = 1.0
                    if current_vol_ratio >= 1.2:
                        bc_pass = True
                        bc_is_exception = True
            
            if not bc_pass:
                continue
            
            # C點新鮮度檢查
            if bars_from_c > self.max_bars_from_c:
                continue
            
            # 返回索引和例外狀態
            return (i-2, i-1, i, ab_is_exception, bc_is_exception)
        
        return None
    
    def calculate_score(self, 
                       retr_pct: float,
                       volume_ratio: float,
                       bars_c_to_signal: int,
                       close_price: float,
                       ema5: float,
                       ema20: float,
                       rsi14: float,
                       daily_change_pct: float) -> Tuple[int, Dict[str, float]]:
        """
        計算 N 字回撤綜合評分 (0-100分)
        """
        breakdown = {}
        
        # 1. 回撤深度分 (40%) - 越接近0.5分數越高
        ideal_retr = 0.5
        retr_distance = abs(retr_pct - ideal_retr)
        retr_score = max(0, 40 * (1 - retr_distance / 0.5))
        breakdown['retracement'] = retr_score
        
        # 2. 量能比分 (25%) - 放量加分
        vol_score = min(25, volume_ratio * 8.33)  # 3.0量比可得滿分25分
        breakdown['volume'] = vol_score
        
        # 3. 反彈早期分 (15%) - 鐘形分佈，5天最優
        def calculate_early_score(days: int) -> float:
            peak, span = 5.0, 6.0   # 5天最優，6天為幅度
            x = max(0.0, 1.0 - abs(days - peak) / span)
            return round(15.0 * x, 2)
        
        early_score = calculate_early_score(bars_c_to_signal)
        breakdown['early_entry'] = early_score
        
        # 4. 均線多頭分 (10%)
        ma_score = 0
        if close_price >= ema5:
            ma_score += 5
        if close_price >= ema20:
            ma_score += 5
        breakdown['moving_average'] = ma_score
        
        # 5. 健康度分 (10%)
        health_score = 0
        if 50 <= rsi14 <= 70:
            health_score += 5
        elif rsi14 > 75:
            health_score -= 2  # 過熱扣分
        elif rsi14 < 45:
            health_score -= 2  # 轉弱扣分
        
        if daily_change_pct > 0.09:  # 單日漲超過9%
            health_score -= 3  # 短期風險扣分
        
        breakdown['health'] = max(0, health_score + 5)  # 基礎5分 + 調整
        
        total_score = sum(breakdown.values())
        return int(round(total_score)), breakdown
    
    def check_trigger_conditions(self, 
                                df: pd.DataFrame,
                                signal_idx: int,
                                ema5: pd.Series,
                                rsi14: pd.Series,
                                volume_ratio: pd.Series) -> Dict[str, bool]:
        """
        檢查三項觸發條件
        """
        triggers = {}
        
        # 條件1: 突破昨高
        if signal_idx > 0:
            yesterday_high = df.iloc[signal_idx - 1]['high']
            today_close = df.iloc[signal_idx]['close']
            triggers['break_yesterday_high'] = today_close > yesterday_high
        else:
            triggers['break_yesterday_high'] = False
        
        # 條件2: 量增上穿 EMA5
        today_close = df.iloc[signal_idx]['close']
        today_ema5 = ema5.iloc[signal_idx]
        today_vol_ratio = volume_ratio.iloc[signal_idx]
        triggers['ema5_volume'] = (today_close > today_ema5) and (today_vol_ratio > self.volume_threshold)
        
        # 條件3: RSI 強勢
        today_rsi = rsi14.iloc[signal_idx]
        triggers['rsi_strong'] = today_rsi >= 50
        
        return triggers
    
    def detect_n_pattern(self, df: pd.DataFrame, stock_id: str) -> Optional[NPatternSignal]:
        """
        偵測單一股票的 N 字回撤形態
        
        Args:
            df: 股價數據，包含 date, open, high, low, close, volume
            stock_id: 股票代碼
            
        Returns:
            NPatternSignal or None
        """
        if len(df) < self.lookback_bars // 2:
            logger.warning(f"{stock_id}: 數據不足，需要至少 {self.lookback_bars//2} 筆")
            return None
        
        # 確保數據按日期排序
        df = df.sort_values('date').reset_index(drop=True)
        
        # 限制回看範圍
        lookback_df = df.tail(self.lookback_bars).reset_index(drop=True)
        
        # 計算技術指標
        ema5 = self.indicators.ema(lookback_df['close'], self.ema_len)
        ema20 = self.indicators.ema(lookback_df['close'], self.ema20_len)
        rsi14 = self.indicators.rsi_wilder(lookback_df['close'], self.rsi_len)
        volume_ratio = self.indicators.volume_ratio(lookback_df['volume'], self.vol_ma_len)
        
        # ZigZag 偵測 - 使用動態門檻
        if self.use_dynamic_zigzag:
            # 計算動態門檻 (使用外掛參數)
            dynamic_threshold = self.indicators.dynamic_zigzag_threshold(
                lookback_df['close'], lookback_df['high'], lookback_df['low'],
                period=self.atr_len, smooth_period=self.atr_smooth,
                atr_multiplier=self.atr_multiplier, floor=self.zigzag_floor, cap=self.zigzag_cap
            )
            # 使用最新的動態門檻 (Fallback保護)
            latest = dynamic_threshold.iloc[-1]
            latest_threshold = latest if not pd.isna(latest) else self.zigzag_change_pct
            self.zigzag = ZigZagDetector(min_change_pct=latest_threshold)
        else:
            self.zigzag = ZigZagDetector(min_change_pct=self.zigzag_change_pct)
        
        zigzag_points = self.zigzag.detect(lookback_df)
        if len(zigzag_points) < 3:
            logger.debug(f"{stock_id}: ZigZag 轉折點不足")
            return None
        
        # 尋找 ABC 形態 (含例外狀態)
        abc_result = self.find_last_abc_pattern(zigzag_points, lookback_df)
        if abc_result is None:
            logger.debug(f"{stock_id}: 未找到符合條件的 ABC 形態")
            return None
        
        A_idx, B_idx, C_idx, ab_is_exception, bc_is_exception = abc_result
        
        # 提取 ABC 點資訊
        A_price = zigzag_points[A_idx][1]
        A_date = lookback_df.iloc[zigzag_points[A_idx][0]]['date']
        B_price = zigzag_points[B_idx][1]
        B_date = lookback_df.iloc[zigzag_points[B_idx][0]]['date']
        C_price = zigzag_points[C_idx][1]
        C_date = lookback_df.iloc[zigzag_points[C_idx][0]]['date']
        
        # 計算形態參數 (除零保護)
        eps = 1e-9
        rise_pct = (B_price - A_price) / max(A_price, eps)
        retr_pct = (B_price - C_price) / max(B_price - A_price, eps)
        bars_ab = zigzag_points[B_idx][0] - zigzag_points[A_idx][0]
        bars_bc = zigzag_points[C_idx][0] - zigzag_points[B_idx][0]
        bars_c_to_signal = len(lookback_df) - 1 - zigzag_points[C_idx][0]
        
        # 使用最後一日作為訊號日
        signal_idx = len(lookback_df) - 1
        signal_date = lookback_df.iloc[signal_idx]['date']
        
        # 檢查觸發條件
        triggers = self.check_trigger_conditions(
            lookback_df, signal_idx, ema5, rsi14, volume_ratio
        )
        
        # 必須至少一個觸發條件成立
        if not any(triggers.values()):
            logger.debug(f"{stock_id}: 無觸發條件成立")
            return None
        
        # 計算當日技術指標值
        today_ema5 = ema5.iloc[signal_idx] if not pd.isna(ema5.iloc[signal_idx]) else 0
        today_ema20 = ema20.iloc[signal_idx] if not pd.isna(ema20.iloc[signal_idx]) else 0
        today_rsi = rsi14.iloc[signal_idx] if not pd.isna(rsi14.iloc[signal_idx]) else 50
        today_vol_ratio = volume_ratio.iloc[signal_idx] if not pd.isna(volume_ratio.iloc[signal_idx]) else 1.0
        
        # 計算單日漲跌幅
        if signal_idx > 0:
            yesterday_close = lookback_df.iloc[signal_idx - 1]['close']
            today_close = lookback_df.iloc[signal_idx]['close']
            daily_change_pct = (today_close - yesterday_close) / yesterday_close
        else:
            daily_change_pct = 0
        
        # 計算評分
        score, score_breakdown = self.calculate_score(
            retr_pct, today_vol_ratio, bars_c_to_signal,
            lookback_df.iloc[signal_idx]['close'], today_ema5, today_ema20,
            today_rsi, daily_change_pct
        )
        
        # 建立訊號 (含例外狀態)
        signal = NPatternSignal(
            stock_id=stock_id,
            signal_date=signal_date,
            A_price=A_price,
            A_date=A_date,
            B_price=B_price,
            B_date=B_date,
            C_price=C_price,
            C_date=C_date,
            rise_pct=rise_pct,
            retr_pct=retr_pct,
            bars_ab=bars_ab,
            bars_bc=bars_bc,
            bars_c_to_signal=bars_c_to_signal,
            ab_is_exception=ab_is_exception,
            bc_is_exception=bc_is_exception,
            ema5=today_ema5,
            ema20=today_ema20,
            rsi14=today_rsi,
            volume_ratio=today_vol_ratio,
            trigger_break_yesterday_high=triggers['break_yesterday_high'],
            trigger_ema5_volume=triggers['ema5_volume'],
            trigger_rsi_strong=triggers['rsi_strong'],
            score=score,
            score_breakdown=score_breakdown
        )
        
        return signal

if __name__ == "__main__":
    # 簡單測試
    logging.basicConfig(level=logging.INFO)
    
    # 模擬數據測試
    dates = pd.date_range('2025-01-01', periods=100, freq='D')
    np.random.seed(42)
    
    # 模擬股價走勢：上漲->回撤->反彈
    prices = []
    base_price = 100
    
    # A到B：上漲30%
    for i in range(30):
        base_price *= (1 + np.random.normal(0.01, 0.02))
        prices.append(base_price)
    
    # B到C：回撤50%
    peak_price = base_price
    for i in range(15):
        base_price *= (1 + np.random.normal(-0.015, 0.01))
        prices.append(base_price)
    
    # C之後：反彈
    for i in range(55):
        base_price *= (1 + np.random.normal(0.005, 0.015))
        prices.append(base_price)
    
    # 構建DataFrame
    df = pd.DataFrame({
        'date': dates.strftime('%Y-%m-%d'),
        'open': prices,
        'high': [p * (1 + abs(np.random.normal(0, 0.01))) for p in prices],
        'low': [p * (1 - abs(np.random.normal(0, 0.01))) for p in prices],
        'close': prices,
        'volume': [int(1000000 * (1 + np.random.normal(0, 0.3))) for _ in prices]
    })
    
    # 測試偵測器
    detector = NPatternDetector()
    signal = detector.detect_n_pattern(df, "TEST")
    
    if signal:
        print(f"✅ 偵測到 N 字回撤訊號:")
        print(f"   股票: {signal.stock_id}")
        print(f"   日期: {signal.signal_date}")
        print(f"   A點: {signal.A_price:.2f} ({signal.A_date})")
        print(f"   B點: {signal.B_price:.2f} ({signal.B_date})")
        print(f"   C點: {signal.C_price:.2f} ({signal.C_date})")
        print(f"   漲幅: {signal.rise_pct:.1%}")
        print(f"   回撤: {signal.retr_pct:.1%}")
        print(f"   評分: {signal.score}/100")
        print(f"   觸發: 昨高={signal.trigger_break_yesterday_high}, "
              f"EMA5量={signal.trigger_ema5_volume}, RSI={signal.trigger_rsi_strong}")
    else:
        print("❌ 未偵測到 N 字回撤訊號")