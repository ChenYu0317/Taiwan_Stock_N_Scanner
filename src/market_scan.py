#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
台股N字回撤市場掃描器 - 主程式
統一的全市場掃描工具，使用最優化參數配置
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'signal'))
from n_pattern_detector import NPatternDetector

import pandas as pd
import sqlite3
from datetime import datetime

def main():
    """主掃描函數"""
    print("🚀 台股N字回撤市場掃描器")
    print("="*60)
    
    # 使用最優化參數配置
    detector = NPatternDetector(
        lookback_bars=60,
        zigzag_change_pct=0.015,  # 1.5% ZigZag敏感度（最優）
        min_leg_pct=0.04,         # 4% 最小波段（最優）
        retr_min=0.20,            # 20% 最小回撤
        retr_max=0.80,            # 80% 最大回撤  
        c_tolerance=0.00,         # C不可破A
        min_bars_ab=1,            # AB最少1天（最優，不過度限制）
        max_bars_ab=80,           # AB最多80天
        min_bars_bc=1,            # BC最少1天
        max_bars_bc=50,           # BC最多50天
        volume_threshold=1.0      # 量能門檻1.0（最優）
    )
    
    print("📊 參數配置:")
    print(f"   ZigZag敏感度: {detector.zigzag_change_pct:.1%}")
    print(f"   最小波段漲幅: {detector.min_leg_pct:.1%}")
    print(f"   回撤範圍: {detector.retr_min:.0%}-{detector.retr_max:.0%}")
    print(f"   時間護欄: AB={detector.min_bars_ab}-{detector.max_bars_ab}天, BC={detector.min_bars_bc}-{detector.max_bars_bc}天")
    print(f"   量能門檻: {detector.volume_threshold:.1f}倍")
    print()
    
    # 獲取股票清單
    signals = []
    conn = sqlite3.connect('data/cleaned/taiwan_stocks_cleaned.db')
    
    # 獲取所有有足夠數據的股票
    stock_query = """
    SELECT DISTINCT stock_id, COUNT(*) as record_count
    FROM daily_prices
    GROUP BY stock_id
    HAVING COUNT(*) >= 60
    ORDER BY stock_id
    """
    
    stock_result = pd.read_sql_query(stock_query, conn)
    all_stocks = stock_result['stock_id'].tolist()
    
    print(f"開始掃描 {len(all_stocks)} 檔股票...")
    print("-" * 60)
    
    # 統計變量
    total_tested = 0
    zigzag_adequate = 0
    abc_found = 0
    
    for i, stock_id in enumerate(all_stocks):
        if i % 20 == 0:  # 每20檔顯示進度
            print(f"進度: {i}/{len(all_stocks)} ({i/len(all_stocks)*100:.1f}%)")
        
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
                continue
            
            total_tested += 1
            recent_df = df.tail(60).reset_index(drop=True)
            
            # ZigZag檢查
            zigzag_points = detector.zigzag.detect(recent_df)
            
            if len(zigzag_points) >= 3:
                zigzag_adequate += 1
                
                # ABC檢查
                abc_result = detector.find_last_abc_pattern(zigzag_points, recent_df)
                if abc_result:
                    abc_found += 1
                    
                    # 完整偵測
                    signal = detector.detect_n_pattern(df, stock_id)
                    
                    if signal:
                        signals.append(signal)
                        print(f"✅ {stock_id}: {signal.score}分 (漲{signal.rise_pct:.1%}→撤{signal.retr_pct:.1%})")
        
        except Exception as e:
            continue
    
    conn.close()
    
    # 結果統計報告
    print("\n" + "="*60)
    print("🎯 掃描結果統計")
    print("="*60)
    print(f"總掃描股票: {len(all_stocks)}")
    print(f"ZigZag轉折充足: {zigzag_adequate} ({zigzag_adequate/total_tested*100:.1f}%)")
    print(f"找到ABC形態: {abc_found} ({abc_found/total_tested*100:.1f}%)")
    print(f"產生最終訊號: {len(signals)} ({len(signals)/total_tested*100:.1f}%)")
    
    if not signals:
        print("\n❌ 未發現符合條件的N字回撤訊號")
        return
    
    # 按評分排序
    sorted_signals = sorted(signals, key=lambda s: s.score, reverse=True)
    
    print(f"\n🏆 發現 {len(signals)} 個N字回撤訊號:")
    print("-"*80)
    print(f"{'排名':<4} {'股票':<8} {'評分':<6} {'漲幅':<8} {'回撤':<8} {'A點日期':<12} {'C點日期':<12} {'觸發條件'}")
    print("-"*80)
    
    for i, signal in enumerate(sorted_signals, 1):
        triggers = []
        if signal.trigger_break_yesterday_high:
            triggers.append("昨高")
        if signal.trigger_ema5_volume:
            triggers.append("EMA5量")
        if signal.trigger_rsi_strong:
            triggers.append("RSI")
        
        trigger_str = ",".join(triggers)
        
        print(f"{i:<4} {signal.stock_id:<8} {signal.score:<6} "
              f"{signal.rise_pct:.1%}  {signal.retr_pct:.1%}  "
              f"{signal.A_date:<12} {signal.C_date:<12} {trigger_str}")
    
    # 詳細前10名分析
    print(f"\n📊 前10名詳細分析:")
    print("-"*80)
    
    for i, signal in enumerate(sorted_signals[:10], 1):
        print(f"\n{i}. {signal.stock_id} - {signal.score}分")
        print(f"   📈 N字形態: {signal.A_price:.1f}({signal.A_date}) → {signal.B_price:.1f}({signal.B_date}) → {signal.C_price:.1f}({signal.C_date})")
        print(f"   📊 幅度統計: 上漲{signal.rise_pct:.1%}, 回撤{signal.retr_pct:.1%}")
        print(f"   🎯 技術指標: RSI={signal.rsi14:.1f}, EMA5={signal.ema5:.1f}, 量比={signal.volume_ratio:.2f}")
        print(f"   ✅ 觸發條件: 昨高突破={signal.trigger_break_yesterday_high}, EMA5量增={signal.trigger_ema5_volume}, RSI強勢={signal.trigger_rsi_strong}")
        print(f"   📝 評分組成: {signal.score_breakdown}")
    
    # 統計特徵分析
    if len(signals) > 1:
        scores = [s.score for s in signals]
        rises = [s.rise_pct for s in signals] 
        retrs = [s.retr_pct for s in signals]
        rsis = [s.rsi14 for s in signals]
        
        print(f"\n📈 訊號統計特徵:")
        print("--" * 25)
        print(f"評分分布: {min(scores)}-{max(scores)} (平均: {sum(scores)/len(scores):.1f})")
        print(f"漲幅分布: {min(rises):.1%}-{max(rises):.1%} (平均: {sum(rises)/len(rises):.1%})")
        print(f"回撤分布: {min(retrs):.1%}-{max(retrs):.1%} (平均: {sum(retrs)/len(retrs):.1%})")
        print(f"RSI分布: {min(rsis):.1f}-{max(rsis):.1f} (平均: {sum(rsis)/len(rsis):.1f})")
        
        # 觸發條件統計
        break_count = sum(1 for s in signals if s.trigger_break_yesterday_high)
        ema_count = sum(1 for s in signals if s.trigger_ema5_volume)
        rsi_count = sum(1 for s in signals if s.trigger_rsi_strong)
        
        print(f"\n觸發條件分布:")
        print(f"突破昨高: {break_count}/{len(signals)} ({break_count/len(signals)*100:.1f}%)")
        print(f"EMA5量增: {ema_count}/{len(signals)} ({ema_count/len(signals)*100:.1f}%)")
        print(f"RSI強勢: {rsi_count}/{len(signals)} ({rsi_count/len(signals)*100:.1f}%)")
    
    print(f"\n🎉 掃描完成！共發現 {len(signals)} 個N字回撤訊號")
    print(f"⏰ 掃描時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()