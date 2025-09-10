#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
診斷原始標準為什麼找不到任何訊號
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'signal'))
from n_pattern_detector import NPatternDetector

import pandas as pd
import sqlite3

def diagnose_zigzag_sensitivity():
    """診斷ZigZag敏感度問題"""
    print("🔍 診斷ZigZag敏感度問題")
    
    # 測試不同敏感度對台積電的影響
    conn = sqlite3.connect('data/cleaned/taiwan_stocks_cleaned.db')
    query = """
    SELECT date, open, high, low, close, volume
    FROM daily_prices 
    WHERE stock_id = ?
    ORDER BY date
    """
    df = pd.read_sql_query(query, conn, params=('2330',))
    conn.close()
    
    recent_df = df.tail(60).reset_index(drop=True)
    price_range = recent_df['close'].max() - recent_df['close'].min()
    avg_price = recent_df['close'].mean()
    
    print(f"📊 台積電(2330) 60日數據分析:")
    print(f"   價格範圍: {recent_df['close'].min():.0f} ~ {recent_df['close'].max():.0f}")
    print(f"   價格區間: {price_range:.0f} 元")
    print(f"   平均價格: {avg_price:.0f} 元")
    print(f"   波動率: {price_range/avg_price:.1%}")
    
    # 測試不同ZigZag參數
    test_params = [0.01, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05]
    
    print(f"\n🔄 不同ZigZag敏感度測試:")
    for pct in test_params:
        from n_pattern_detector import ZigZagDetector
        zigzag = ZigZagDetector(min_change_pct=pct)
        points = zigzag.detect(recent_df)
        
        print(f"   {pct:.1%} 閾值 → {len(points):2d} 個轉折點", end="")
        if len(points) >= 3:
            print(" ✅")
        else:
            print(" ❌")

def test_looser_standards_progressively():
    """逐步放寬標準測試"""
    print(f"\n🎯 逐步放寬標準測試")
    
    test_stocks = ['2330', '2454', '2317', '3008', '6505', '2408', '2356', '2409']
    
    # 測試配置
    configs = [
        {"name": "原始嚴格", "zigzag": 0.03, "min_leg": 0.05, "tolerance": 0.00},
        {"name": "ZigZag放寬", "zigzag": 0.02, "min_leg": 0.05, "tolerance": 0.00},
        {"name": "波段放寬", "zigzag": 0.03, "min_leg": 0.03, "tolerance": 0.00},
        {"name": "容忍度放寬", "zigzag": 0.03, "min_leg": 0.05, "tolerance": 0.03},
        {"name": "綜合放寬", "zigzag": 0.02, "min_leg": 0.03, "tolerance": 0.02},
    ]
    
    conn = sqlite3.connect('data/cleaned/taiwan_stocks_cleaned.db')
    
    for config in configs:
        print(f"\n📊 測試配置: {config['name']}")
        print(f"   ZigZag: {config['zigzag']:.1%}, 最小波段: {config['min_leg']:.1%}, 容忍度: {config['tolerance']:.1%}")
        
        detector = NPatternDetector(
            lookback_bars=60,
            min_leg_pct=config['min_leg'],
            retr_min=0.20,
            retr_max=0.80,
            c_tolerance=config['tolerance']
        )
        detector.zigzag.min_change_pct = config['zigzag']
        
        signals = 0
        zigzag_ok = 0
        abc_found = 0
        
        for stock_id in test_stocks:
            try:
                query = """
                SELECT date, open, high, low, close, volume
                FROM daily_prices 
                WHERE stock_id = ?
                ORDER BY date
                """
                df = pd.read_sql_query(query, conn, params=(stock_id,))
                
                if len(df) < 60:
                    continue
                
                recent_df = df.tail(60).reset_index(drop=True)
                zigzag_points = detector.zigzag.detect(recent_df)
                
                if len(zigzag_points) >= 3:
                    zigzag_ok += 1
                    
                    abc_result = detector.find_last_abc_pattern(zigzag_points, recent_df)
                    if abc_result:
                        abc_found += 1
                        
                        signal = detector.detect_n_pattern(df, stock_id)
                        if signal:
                            signals += 1
                            print(f"      ✅ {stock_id}: 評分{signal.score}")
                
            except Exception as e:
                continue
        
        print(f"   結果: ZigZag足夠={zigzag_ok}, ABC形態={abc_found}, 最終訊號={signals}")
    
    conn.close()

def analyze_market_conditions():
    """分析當前市場條件是否適合N字形態"""
    print(f"\n📈 分析當前市場條件")
    
    conn = sqlite3.connect('data/cleaned/taiwan_stocks_cleaned.db')
    
    # 分析幾檔代表性股票的走勢特徵
    stocks = ['2330', '2454', '2317']
    
    for stock_id in stocks:
        query = """
        SELECT date, close
        FROM daily_prices 
        WHERE stock_id = ?
        ORDER BY date
        """
        df = pd.read_sql_query(query, conn, params=(stock_id,))
        recent_df = df.tail(60)
        
        # 計算趨勢特徵
        start_price = recent_df['close'].iloc[0]
        end_price = recent_df['close'].iloc[-1]
        total_return = (end_price - start_price) / start_price
        
        # 計算最大回撤
        cumulative_max = recent_df['close'].cummax()
        drawdowns = (recent_df['close'] - cumulative_max) / cumulative_max
        max_drawdown = drawdowns.min()
        
        # 計算波動度
        daily_returns = recent_df['close'].pct_change()
        volatility = daily_returns.std() * (252 ** 0.5)  # 年化波動率
        
        print(f"\n📊 {stock_id} 60日走勢特徵:")
        print(f"   總報酬: {total_return:.1%}")
        print(f"   最大回撤: {max_drawdown:.1%}")
        print(f"   年化波動率: {volatility:.1%}")
        
        # 判斷走勢類型
        if abs(total_return) < 0.05:
            trend_type = "盤整"
        elif total_return > 0.15:
            trend_type = "強勢上漲"
        elif total_return < -0.15:
            trend_type = "明顯下跌"
        else:
            trend_type = "溫和趨勢"
        
        print(f"   走勢類型: {trend_type}")
        
        # N字形態適合的市場條件
        if trend_type in ["盤整", "溫和趨勢"] and abs(max_drawdown) > 0.05:
            print(f"   ✅ 適合N字形態")
        else:
            print(f"   ❌ 不太適合N字形態")
    
    conn.close()

if __name__ == "__main__":
    diagnose_zigzag_sensitivity()
    test_looser_standards_progressively() 
    analyze_market_conditions()