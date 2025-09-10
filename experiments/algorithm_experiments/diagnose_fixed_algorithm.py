#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
診斷修正後演算法為何過於嚴格
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'signal'))
from n_pattern_detector import NPatternDetector

import pandas as pd
import sqlite3

def diagnose_strictness():
    """診斷修正後演算法的嚴格程度"""
    print("🔍 診斷修正後演算法過於嚴格的問題")
    
    # 測試不同配置
    configs = [
        {
            "name": "原始bug版本近似", 
            "zigzag_pct": 0.015,
            "min_bars_ab": 1, "max_bars_ab": 200,
            "min_bars_bc": 1, "max_bars_bc": 200,
            "volume_threshold": 1.0
        },
        {
            "name": "修正版本(當前)",
            "zigzag_pct": 0.015,
            "min_bars_ab": 3, "max_bars_ab": 60,
            "min_bars_bc": 2, "max_bars_bc": 40,
            "volume_threshold": 1.2
        },
        {
            "name": "適中版本",
            "zigzag_pct": 0.02,
            "min_bars_ab": 2, "max_bars_ab": 80,
            "min_bars_bc": 1, "max_bars_bc": 50,
            "volume_threshold": 1.1
        }
    ]
    
    test_stocks = ['2330', '2454', '2204', '2409', '2369']
    conn = sqlite3.connect('data/cleaned/taiwan_stocks_cleaned.db')
    
    for config in configs:
        print(f"\n📊 測試配置: {config['name']}")
        print(f"   ZigZag: {config['zigzag_pct']:.1%}")
        print(f"   時間護欄: AB={config['min_bars_ab']}-{config['max_bars_ab']}, BC={config['min_bars_bc']}-{config['max_bars_bc']}")
        print(f"   量能門檻: {config['volume_threshold']}")
        
        detector = NPatternDetector(
            lookback_bars=60,
            zigzag_change_pct=config['zigzag_pct'],
            min_leg_pct=0.04,
            retr_min=0.20,
            retr_max=0.80,
            c_tolerance=0.00,
            min_bars_ab=config['min_bars_ab'],
            max_bars_ab=config['max_bars_ab'],
            min_bars_bc=config['min_bars_bc'],
            max_bars_bc=config['max_bars_bc'],
            volume_threshold=config['volume_threshold']
        )
        
        zigzag_ok = 0
        abc_found = 0
        signals = 0
        
        for stock_id in test_stocks:
            try:
                query = """
                SELECT date, open, high, low, close, volume
                FROM daily_prices WHERE stock_id = ? ORDER BY date
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
                            print(f"      ✅ {stock_id}: {signal.score}分")
            
            except Exception as e:
                continue
        
        print(f"   結果: ZigZag充足={zigzag_ok}/5, ABC形態={abc_found}/5, 最終訊號={signals}/5")
    
    conn.close()

def detailed_failure_analysis():
    """詳細分析失敗原因"""
    print(f"\n🔬 詳細失敗分析")
    
    # 以2454為例進行逐步分析
    stock_id = '2454'
    
    conn = sqlite3.connect('data/cleaned/taiwan_stocks_cleaned.db')
    query = """
    SELECT date, open, high, low, close, volume
    FROM daily_prices WHERE stock_id = ? ORDER BY date
    """
    df = pd.read_sql_query(query, conn, params=(stock_id,))
    conn.close()
    
    print(f"📊 分析 {stock_id} 的失敗原因")
    
    recent_df = df.tail(60).reset_index(drop=True)
    
    # 測試不同ZigZag敏感度
    zigzag_tests = [0.015, 0.02, 0.025, 0.03]
    
    for pct in zigzag_tests:
        detector = NPatternDetector(zigzag_change_pct=pct)
        zigzag_points = detector.zigzag.detect(recent_df)
        
        print(f"\n🔄 ZigZag {pct:.1%}: {len(zigzag_points)} 個轉折點")
        
        if len(zigzag_points) >= 6:  # 顯示最後6個
            print("   最後6個轉折點:")
            for i, (idx, price, type_) in enumerate(zigzag_points[-6:]):
                date = recent_df.iloc[idx]['date']
                print(f"     {type_} {price:.1f} ({date})")
        
        # 檢查ABC形態
        if len(zigzag_points) >= 3:
            # 手動檢查L-H-L模式
            lhl_count = 0
            for i in range(len(zigzag_points)-1, 1, -1):
                if i < 2:
                    break
                if (zigzag_points[i][2] == 'L' and
                    zigzag_points[i-1][2] == 'H' and
                    zigzag_points[i-2][2] == 'L'):
                    
                    A_idx, A_price, _ = zigzag_points[i-2]
                    B_idx, B_price, _ = zigzag_points[i-1]
                    C_idx, C_price, _ = zigzag_points[i]
                    
                    rise_pct = (B_price - A_price) / A_price
                    retr_pct = (B_price - C_price) / (B_price - A_price)
                    bars_ab = B_idx - A_idx
                    bars_bc = C_idx - B_idx
                    bars_from_c = len(recent_df) - 1 - C_idx
                    
                    print(f"     L-H-L候選 #{lhl_count+1}:")
                    print(f"       A={A_price:.1f} B={B_price:.1f} C={C_price:.1f}")
                    print(f"       漲幅={rise_pct:.1%} (需要>5%)")
                    print(f"       回撤={retr_pct:.1%} (需要20-80%)")
                    print(f"       時間: AB={bars_ab}天, BC={bars_bc}天, C到今={bars_from_c}天")
                    
                    # 檢查每個條件
                    checks = []
                    if rise_pct >= 0.05:
                        checks.append("✅漲幅")
                    else:
                        checks.append("❌漲幅")
                    
                    if 0.20 <= retr_pct <= 0.80:
                        checks.append("✅回撤")
                    else:
                        checks.append("❌回撤")
                    
                    if C_price >= A_price:
                        checks.append("✅C>A")
                    else:
                        checks.append("❌C<A")
                    
                    if bars_from_c <= 30:
                        checks.append("✅時效")
                    else:
                        checks.append("❌時效")
                    
                    print(f"       檢查: {' '.join(checks)}")
                    
                    lhl_count += 1
                    if lhl_count >= 2:  # 只顯示前2個
                        break

def find_optimal_parameters():
    """尋找最優參數"""
    print(f"\n🎯 尋找最優參數組合")
    
    # 測試參數組合
    zigzag_options = [0.015, 0.02, 0.025]
    min_bars_ab_options = [1, 2, 3]
    volume_threshold_options = [1.0, 1.1, 1.2]
    
    best_config = None
    best_signals = 0
    
    conn = sqlite3.connect('data/cleaned/taiwan_stocks_cleaned.db')
    test_stocks = ['2330', '2454', '2204', '2409', '2369', '1476', '4967', '6531']
    
    for zigzag_pct in zigzag_options:
        for min_ab in min_bars_ab_options:
            for vol_threshold in volume_threshold_options:
                detector = NPatternDetector(
                    lookback_bars=60,
                    zigzag_change_pct=zigzag_pct,
                    min_leg_pct=0.04,
                    retr_min=0.20,
                    retr_max=0.80,
                    c_tolerance=0.00,
                    min_bars_ab=min_ab,
                    max_bars_ab=80,
                    min_bars_bc=1,
                    max_bars_bc=50,
                    volume_threshold=vol_threshold
                )
                
                signals = 0
                for stock_id in test_stocks:
                    try:
                        query = """
                        SELECT date, open, high, low, close, volume
                        FROM daily_prices WHERE stock_id = ? ORDER BY date
                        """
                        df = pd.read_sql_query(query, conn, params=(stock_id,))
                        
                        if len(df) >= 60:
                            signal = detector.detect_n_pattern(df, stock_id)
                            if signal:
                                signals += 1
                    except:
                        continue
                
                if signals > best_signals:
                    best_signals = signals
                    best_config = {
                        'zigzag_pct': zigzag_pct,
                        'min_bars_ab': min_ab,
                        'volume_threshold': vol_threshold
                    }
                
                if signals > 0:
                    print(f"📊 ZigZag={zigzag_pct:.1%}, min_AB={min_ab}, 量能={vol_threshold}: {signals}/{len(test_stocks)} 訊號")
    
    conn.close()
    
    if best_config:
        print(f"\n🏆 最佳配置:")
        print(f"   ZigZag敏感度: {best_config['zigzag_pct']:.1%}")
        print(f"   AB最小天數: {best_config['min_bars_ab']}")
        print(f"   量能門檻: {best_config['volume_threshold']}")
        print(f"   測試集訊號數: {best_signals}/{len(test_stocks)}")
    
    return best_config

if __name__ == "__main__":
    diagnose_strictness()
    detailed_failure_analysis()
    best = find_optimal_parameters()