#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試 A 級優化效果：速率限制 + 移除冗餘sleep
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from price_data_pipeline import TaiwanStockPriceDataPipeline
import time

def test_optimization():
    """測試優化效果"""
    print("🧪 測試 A 級優化效果")
    print("=" * 40)
    
    # 測試少量股票看速度
    test_stocks = ['1101', '1102', '1103']  # 3檔知名股票
    
    pipeline = TaiwanStockPriceDataPipeline('data/cleaned/taiwan_stocks_cleaned.db')
    
    print(f"測試股票: {test_stocks}")
    print("開始計時...")
    
    start_time = time.time()
    
    try:
        success, failed = pipeline.run_price_data_pipeline(
            max_stocks=len(test_stocks),
            target_bars=60,
            specific_stocks=test_stocks
        )
        
        elapsed_time = time.time() - start_time
        
        print(f"\n📊 測試結果:")
        print(f"  執行時間: {elapsed_time:.1f} 秒")
        print(f"  處理結果: 成功{success}檔, 失敗{failed}檔")
        print(f"  平均每檔: {elapsed_time/len(test_stocks):.1f} 秒")
        
        if elapsed_time < 60:  # 如果少於1分鐘
            print("✅ A級優化成功! 速度明顯提升")
        else:
            print("⚠️ 仍需進一步優化")
            
    except Exception as e:
        print(f"❌ 測試失敗: {e}")

if __name__ == "__main__":
    test_optimization()