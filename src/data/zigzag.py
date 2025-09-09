#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZigZag 轉折點偵測算法
用於識別價格的重要轉折點，作為 ABC 形態識別的基礎
"""

import numpy as np
import pandas as pd
from typing import List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class ZigZagDetector:
    """ZigZag 轉折點偵測器"""
    
    def __init__(self, min_change_pct: float = 0.08):
        """
        初始化 ZigZag 偵測器
        
        Args:
            min_change_pct: 最小變化百分比 (預設 8%)
        """
        self.min_change_pct = min_change_pct
    
    def detect_zigzag_points(self, df: pd.DataFrame) -> List[dict]:
        """
        偵測 ZigZag 轉折點
        
        Args:
            df: DataFrame with columns ['date', 'high', 'low', 'close']
            
        Returns:
            List of pivot points with format:
            [{'index': int, 'date': str, 'price': float, 'type': 'high'|'low'}, ...]
        """
        if len(df) < 3:
            return []
            
        pivots = []
        
        # 確保資料按日期排序
        df = df.sort_values('date').reset_index(drop=True)
        
        # 找第一個起始點
        current_trend = None  # 'up' or 'down'
        last_pivot_idx = 0
        last_pivot_price = df.iloc[0]['close']
        last_pivot_type = 'start'
        
        for i in range(1, len(df)):
            current_high = df.iloc[i]['high']
            current_low = df.iloc[i]['low']
            
            # 計算相對於上一個pivot的變化
            high_change = (current_high - last_pivot_price) / last_pivot_price
            low_change = (last_pivot_price - current_low) / last_pivot_price
            
            if current_trend is None or current_trend == 'up':
                # 尋找高點
                if high_change >= self.min_change_pct:
                    # 更新高點
                    if not pivots or pivots[-1]['type'] != 'high':
                        # 新高點
                        pivots.append({
                            'index': i,
                            'date': df.iloc[i]['date'],
                            'price': current_high,
                            'type': 'high'
                        })
                        last_pivot_idx = i
                        last_pivot_price = current_high
                        last_pivot_type = 'high'
                    elif current_high > pivots[-1]['price']:
                        # 更高的高點，更新最後一個高點
                        pivots[-1].update({
                            'index': i,
                            'date': df.iloc[i]['date'],
                            'price': current_high
                        })
                        last_pivot_idx = i
                        last_pivot_price = current_high
                
                # 檢查是否轉為下跌
                if low_change >= self.min_change_pct and last_pivot_type == 'high':
                    current_trend = 'down'
                    
            else:  # current_trend == 'down'
                # 尋找低點
                if low_change >= self.min_change_pct:
                    # 新低點
                    if not pivots or pivots[-1]['type'] != 'low':
                        pivots.append({
                            'index': i,
                            'date': df.iloc[i]['date'],
                            'price': current_low,
                            'type': 'low'
                        })
                        last_pivot_idx = i
                        last_pivot_price = current_low
                        last_pivot_type = 'low'
                    elif current_low < pivots[-1]['price']:
                        # 更低的低點，更新最後一個低點
                        pivots[-1].update({
                            'index': i,
                            'date': df.iloc[i]['date'],
                            'price': current_low
                        })
                        last_pivot_idx = i
                        last_pivot_price = current_low
                
                # 檢查是否轉為上漲
                if high_change >= self.min_change_pct and last_pivot_type == 'low':
                    current_trend = 'up'
        
        return pivots
    
    def find_last_abc_pattern(self, pivots: List[dict]) -> Optional[Tuple[dict, dict, dict]]:
        """
        從轉折點中找出最後一組 ABC 多頭形態
        
        Args:
            pivots: ZigZag 轉折點列表
            
        Returns:
            Tuple of (A, B, C) 或 None 如果找不到
        """
        if len(pivots) < 3:
            return None
        
        # 從後往前找 Low-High-Low 的組合
        for i in range(len(pivots) - 2, 1, -1):
            A = pivots[i-2]
            B = pivots[i-1]  
            C = pivots[i]
            
            # 檢查是否符合 ABC 多頭形態：Low-High-Low
            if (A['type'] == 'low' and 
                B['type'] == 'high' and 
                C['type'] == 'low' and
                A['index'] < B['index'] < C['index']):
                
                # 基本條件檢查
                if self._validate_abc_pattern(A, B, C):
                    return (A, B, C)
        
        return None
    
    def _validate_abc_pattern(self, A: dict, B: dict, C: dict) -> bool:
        """
        驗證 ABC 形態是否符合條件
        
        Args:
            A: 低點 A
            B: 高點 B  
            C: 低點 C
            
        Returns:
            True 如果符合條件
        """
        # 1. 上漲幅度檢查：A 到 B 至少要有足夠漲幅
        rise_pct = (B['price'] - A['price']) / A['price']
        if rise_pct < self.min_change_pct:
            return False
        
        # 2. 回撤檢查：C 必須高於 A (不破前低)
        if C['price'] <= A['price'] * 0.99:  # 允許 1% 容差
            return False
        
        # 3. 回撤比例檢查：30%-70% 是健康回撤
        retracement_pct = (B['price'] - C['price']) / (B['price'] - A['price'])
        if not (0.30 <= retracement_pct <= 0.70):
            return False
        
        # 4. 時間檢查：各段都要有最少天數
        bars_ab = B['index'] - A['index']
        bars_bc = C['index'] - B['index']
        
        if bars_ab < 3 or bars_bc < 2:  # 最少交易日要求
            return False
        
        return True
    
    def analyze_pattern_strength(self, A: dict, B: dict, C: dict) -> dict:
        """
        分析 ABC 形態的強度指標
        
        Returns:
            dict with pattern analysis metrics
        """
        rise_pct = (B['price'] - A['price']) / A['price']
        retr_pct = (B['price'] - C['price']) / (B['price'] - A['price'])
        bars_ab = B['index'] - A['index']
        bars_bc = C['index'] - B['index']
        
        # 回撤深度評分 (越接近 0.5 越好)
        retr_score = 100 * (1 - 2 * abs(retr_pct - 0.5))
        
        # 上漲強度評分
        rise_score = min(100, rise_pct * 500)  # 20% 漲幅 = 100分
        
        # 時間平衡評分
        time_ratio = bars_bc / bars_ab if bars_ab > 0 else 1
        time_score = 100 * (1 - abs(time_ratio - 0.5))  # 理想比例 1:0.5
        
        return {
            'rise_pct': rise_pct,
            'retracement_pct': retr_pct,
            'bars_ab': bars_ab,
            'bars_bc': bars_bc,
            'retracement_score': max(0, retr_score),
            'rise_score': max(0, rise_score),
            'time_score': max(0, time_score),
            'overall_score': (retr_score + rise_score + time_score) / 3
        }

def test_zigzag():
    """測試 ZigZag 功能"""
    # 創建測試資料
    dates = pd.date_range('2024-01-01', periods=60, freq='D')
    
    # 模擬價格：上漲 → 回撤 → 再上漲的模式
    base_price = 100
    prices = []
    
    # A段：低點到高點 (20天，漲20%)
    for i in range(20):
        price = base_price + (i * 1.0)  # 100 → 120
        prices.append(price)
    
    # B段：高點到回撤低點 (15天，跌12%)
    high_price = prices[-1]
    for i in range(15):
        price = high_price - (i * 0.8)  # 120 → 108
        prices.append(price)
    
    # C段後：橫盤整理
    for i in range(25):
        price = 108 + np.random.normal(0, 1)
        prices.append(price)
    
    # 創建DataFrame
    df = pd.DataFrame({
        'date': dates[:len(prices)],
        'high': [p + np.random.uniform(0, 2) for p in prices],
        'low': [p - np.random.uniform(0, 2) for p in prices],
        'close': prices
    })
    
    # 測試ZigZag
    detector = ZigZagDetector(min_change_pct=0.08)
    pivots = detector.detect_zigzag_points(df)
    
    print(f"找到 {len(pivots)} 個轉折點:")
    for pivot in pivots:
        print(f"  {pivot['date']}: {pivot['price']:.2f} ({pivot['type']})")
    
    # 測試ABC形態識別
    abc_pattern = detector.find_last_abc_pattern(pivots)
    if abc_pattern:
        A, B, C = abc_pattern
        print(f"\n找到ABC形態:")
        print(f"  A: {A['date']} = {A['price']:.2f}")
        print(f"  B: {B['date']} = {B['price']:.2f}")  
        print(f"  C: {C['date']} = {C['price']:.2f}")
        
        analysis = detector.analyze_pattern_strength(A, B, C)
        print(f"\n形態分析:")
        print(f"  上漲幅度: {analysis['rise_pct']:.1%}")
        print(f"  回撤比例: {analysis['retracement_pct']:.1%}")
        print(f"  整體評分: {analysis['overall_score']:.1f}")
    else:
        print("未找到符合條件的ABC形態")

if __name__ == "__main__":
    test_zigzag()