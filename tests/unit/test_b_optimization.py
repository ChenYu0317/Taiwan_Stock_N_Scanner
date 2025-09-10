#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試 B 級優化效果：全市場日彙總批次抽取
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from price_data_pipeline import TaiwanStockPriceDataPipeline
import time

def test_b_optimization():
    """測試B級優化效果"""
    print("🧪 測試 B 級優化效果")
    print("=" * 50)
    
    pipeline = TaiwanStockPriceDataPipeline('data/cleaned/taiwan_stocks_cleaned.db')
    
    print("🚀 測試全市場日彙總API...")
    
    # 測試單日數據抓取
    print("\n1️⃣ 測試單日全市場數據抓取")
    start_time = time.time()
    
    daily_data = pipeline.fetch_market_daily_data('20250906')  # 2025年9月6日 (週五)
    
    if daily_data is not None:
        elapsed = time.time() - start_time
        print(f"✅ 成功抓取 {len(daily_data)} 檔股票")
        print(f"⏱️  耗時: {elapsed:.2f} 秒")
        print(f"📊 範例數據: {daily_data.head(3)}")
    else:
        print("❌ 單日數據抓取失敗")
        return
    
    # 測試批次數據抓取（小範圍）
    print("\n2️⃣ 測試批次數據抓取（10個交易日）")
    start_time = time.time()
    
    market_data = pipeline.fetch_market_recent_data_batch(target_bars=10)
    
    if market_data:
        elapsed = time.time() - start_time
        print(f"✅ 成功抓取 {len(market_data)} 檔股票的10日數據")
        print(f"⏱️  耗時: {elapsed:.2f} 秒")
        print(f"📊 平均每檔: {elapsed/len(market_data):.3f} 秒")
        
        # 顯示幾個範例
        sample_stocks = list(market_data.keys())[:3]
        for stock in sample_stocks:
            df = market_data[stock]
            print(f"📈 {stock}: {len(df)} 筆資料 ({df['date'].min()} ~ {df['date'].max()})")
    else:
        print("❌ 批次數據抓取失敗")
        return
    
    # 測試優化版pipeline（小範圍）
    print("\n3️⃣ 測試B級優化版pipeline（前20檔股票）")
    start_time = time.time()
    
    success, failed = pipeline.run_price_data_pipeline_optimized(
        max_stocks=20,
        target_bars=30  # 30日數據測試
    )
    
    elapsed = time.time() - start_time
    print(f"\n📊 B級優化測試結果:")
    print(f"  處理結果: 成功{success}檔, 失敗{failed}檔")
    print(f"  總耗時: {elapsed:.1f} 秒")
    
    if success > 0:
        print(f"  平均每檔: {elapsed/success:.2f} 秒")
        if elapsed < 60:  # 少於1分鐘
            print("🎉 B級優化成功! 速度大幅提升")
        else:
            print("⚠️ 速度提升有限，可能需要C級優化")
    
if __name__ == "__main__":
    test_b_optimization()