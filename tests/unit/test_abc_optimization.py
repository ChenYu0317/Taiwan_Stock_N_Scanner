#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試 A+B+C 級優化完整效果
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from price_data_pipeline import TaiwanStockPriceDataPipeline
import time

def test_abc_optimization():
    """測試ABC級優化完整效果"""
    print("🚀 測試 A+B+C 級優化完整效果")
    print("=" * 60)
    
    pipeline = TaiwanStockPriceDataPipeline('data/cleaned/taiwan_stocks_cleaned.db')
    
    # 測試中等規模數據 - 更符合實際使用
    print("🎯 測試ABC級優化 (50檔股票 × 20個交易日)")
    start_time = time.time()
    
    success, failed = pipeline.run_price_data_pipeline_optimized(
        max_stocks=50,      # 50檔股票
        target_bars=20      # 20個交易日
    )
    
    elapsed = time.time() - start_time
    
    print(f"\n📊 ABC級優化完整測試結果:")
    print(f"  處理結果: 成功{success}檔, 失敗{failed}檔")
    print(f"  總耗時: {elapsed:.1f} 秒")
    
    if success > 0:
        print(f"  平均每檔: {elapsed/(success+failed):.2f} 秒")
        
        # 性能評估
        total_records = success * 20  # 每檔20筆資料
        records_per_sec = total_records / elapsed
        
        print(f"  資料處理速度: {records_per_sec:.0f} 筆/秒")
        
        if elapsed < 60:  # 少於1分鐘
            print("🎉 ABC級優化完全成功!")
            print("📈 已達到生產級性能標準")
            
            # 估算500檔股票的處理時間
            estimated_500_time = (elapsed / 50) * 500
            print(f"📊 估算500檔股票處理時間: {estimated_500_time/60:.1f} 分鐘")
            
            if estimated_500_time < 600:  # 小於10分鐘
                print("✨ 達成 5-10分鐘級 目標!")
            else:
                print("⚠️ 大規模處理可能需要並行化優化")
        else:
            print("⚠️ 性能仍需改善，可能需要並行化")
    else:
        print("❌ ABC級優化失敗，需要調試")

if __name__ == "__main__":
    test_abc_optimization()