#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
N字回撤偵測演算法測試腳本
"""

import sys
import os

# 添加 src 目錄到 Python 路徑
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import pandas as pd
import numpy as np
import sqlite3
import logging

# 導入我們的模組
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'signal'))
from n_pattern_detector import NPatternDetector

# 設置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_with_real_data():
    """使用真實股票數據測試"""
    print("\n=== 使用真實股票數據測試 N字偵測 ===")
    
    # 連接數據庫
    db_path = 'data/cleaned/taiwan_stocks_cleaned.db'
    if not os.path.exists(db_path):
        print(f"❌ 數據庫不存在: {db_path}")
        return
    
    # 獲取測試股票清單（取前10檔）
    test_stocks = ['2330', '2454', '2881', '1101', '3008', '2891', '1303', '1326', '2885', '6505']
    
    detector = NPatternDetector(
        lookback_bars=60,    # 減少到60根
        min_leg_pct=0.04,    # 4%最小波段 (放寬)
        retr_min=0.25,       # 25%最小回撤
        retr_max=0.75        # 75%最大回撤
    )
    
    signals = []
    conn = sqlite3.connect(db_path)
    
    for stock_id in test_stocks:
        print(f"\n📊 測試股票: {stock_id}")
        
        try:
            # 獲取股票數據
            query = """
            SELECT date, open, high, low, close, volume
            FROM daily_prices 
            WHERE stock_id = ?
            ORDER BY date
            """
            df = pd.read_sql_query(query, conn, params=(stock_id,))
            
            if len(df) < 60:
                print(f"   ❌ 數據不足: {len(df)} 筆")
                continue
            
            print(f"   📈 數據範圍: {df['date'].iloc[0]} ~ {df['date'].iloc[-1]} ({len(df)} 筆)")
            
            # 偵測N字形態
            signal = detector.detect_n_pattern(df, stock_id)
            
            if signal:
                signals.append(signal)
                print(f"   ✅ 找到N字訊號!")
                print(f"      A點: {signal.A_price:.2f} ({signal.A_date})")
                print(f"      B點: {signal.B_price:.2f} ({signal.B_date})")
                print(f"      C點: {signal.C_price:.2f} ({signal.C_date})")
                print(f"      漲幅: {signal.rise_pct:.1%}, 回撤: {signal.retr_pct:.1%}")
                print(f"      評分: {signal.score}/100")
                print(f"      觸發條件: 昨高={signal.trigger_break_yesterday_high}, EMA5量={signal.trigger_ema5_volume}, RSI={signal.trigger_rsi_strong}")
            else:
                print(f"   ❌ 未找到N字訊號")
                
        except Exception as e:
            print(f"   ⚠️ 處理錯誤: {e}")
    
    conn.close()
    
    print(f"\n📋 測試結果總結:")
    print(f"   測試股票數: {len(test_stocks)}")
    print(f"   找到訊號數: {len(signals)}")
    print(f"   命中率: {len(signals)/len(test_stocks):.1%}")
    
    # 顯示最高分訊號
    if signals:
        best_signal = max(signals, key=lambda s: s.score)
        print(f"\n🏆 最佳訊號:")
        print(f"   股票: {best_signal.stock_id}")
        print(f"   評分: {best_signal.score}/100")
        print(f"   漲幅: {best_signal.rise_pct:.1%}")
        print(f"   回撤: {best_signal.retr_pct:.1%}")
        
        # 詳細訊號列表
        print(f"\n📊 所有訊號詳情:")
        for i, signal in enumerate(sorted(signals, key=lambda s: s.score, reverse=True), 1):
            print(f"   {i}. {signal.stock_id}: {signal.score}分")
            print(f"      上漲{signal.rise_pct:.1%} → 回撤{signal.retr_pct:.1%}")
            print(f"      量比{signal.volume_ratio:.1f}, RSI{signal.rsi14:.1f}")
    
    return signals

def test_synthetic_data():
    """使用合成數據測試"""
    print("\n=== 使用合成N字數據測試 ===")
    
    # 創建理想的N字形態數據
    np.random.seed(42)
    dates = pd.date_range('2025-08-01', periods=60, freq='D')
    
    prices = []
    base = 100.0
    
    # A點：起始低點 (第5天)
    for i in range(5):
        prices.append(base + np.random.normal(0, 1))
    
    # A到B：上漲15% (10天)
    for i in range(10):
        base *= 1.015  # 每天漲1.5%
        prices.append(base + np.random.normal(0, 0.5))
    
    # B到C：回撤50% (8天)
    peak = base
    for i in range(8):
        base *= 0.94  # 每天跌6%
        prices.append(base + np.random.normal(0, 0.5))
    
    # C之後：準備反彈 (37天)
    bottom = base
    for i in range(37):
        base *= 1.005  # 每天微漲0.5%
        prices.append(base + np.random.normal(0, 0.5))
    
    # 構建完整的K線數據
    df = pd.DataFrame({
        'date': dates.strftime('%Y-%m-%d'),
        'open': prices,
        'high': [max(p, p * (1 + abs(np.random.normal(0, 0.005)))) for p in prices],
        'low': [min(p, p * (1 - abs(np.random.normal(0, 0.005)))) for p in prices],
        'close': prices,
        'volume': [int(1000000 * (1 + np.random.normal(0, 0.2))) for _ in prices]
    })
    
    print(f"📈 合成數據概況:")
    print(f"   數據期間: {df['date'].iloc[0]} ~ {df['date'].iloc[-1]}")
    print(f"   起始價: {df['close'].iloc[4]:.2f}")
    print(f"   峰值價: {max(df['close'][:20]):.2f}")
    print(f"   底部價: {min(df['close'][15:25]):.2f}")
    print(f"   結束價: {df['close'].iloc[-1]:.2f}")
    
    # 使用寬鬆的參數進行測試
    detector = NPatternDetector(
        lookback_bars=60,
        min_leg_pct=0.04,    # 4%最小波段
        retr_min=0.20,       # 20%最小回撤
        retr_max=0.80        # 80%最大回撤
    )
    
    signal = detector.detect_n_pattern(df, "SYNTHETIC")
    
    if signal:
        print(f"\n✅ 成功偵測到合成N字訊號:")
        print(f"   A點: {signal.A_price:.2f} ({signal.A_date})")
        print(f"   B點: {signal.B_price:.2f} ({signal.B_date})")
        print(f"   C點: {signal.C_price:.2f} ({signal.C_date})")
        print(f"   漲幅: {signal.rise_pct:.1%}")
        print(f"   回撤: {signal.retr_pct:.1%}")
        print(f"   評分: {signal.score}/100")
        print(f"   分數詳細: {signal.score_breakdown}")
    else:
        print(f"❌ 未能偵測到合成N字訊號")
        
        # 調試：檢查ZigZag點
        zigzag_points = detector.zigzag.detect(df)
        print(f"\n🔍 ZigZag偵測結果 ({len(zigzag_points)} 個轉折點):")
        for i, (idx, price, type_) in enumerate(zigzag_points[-6:]):  # 顯示最後6個點
            date = df.iloc[idx]['date']
            print(f"   {i}: {type_} @ {price:.2f} ({date})")

if __name__ == "__main__":
    print("🚀 開始N字回撤偵測演算法測試")
    
    # 先測試合成數據
    test_synthetic_data()
    
    # 再測試真實數據
    test_with_real_data()
    
    print("\n✅ 測試完成!")