#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試替代 API 方案
"""

import requests
import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_twse_all_market():
    """測試 TWSE 全市場數據"""
    
    logger.info("🧪 測試 TWSE OpenAPI 全市場數據")
    
    url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"✅ TWSE OpenAPI 成功")
        logger.info(f"📊 數據筆數: {len(data) if isinstance(data, list) else 'Unknown'}")
        
        if isinstance(data, list) and len(data) > 0:
            logger.info(f"📋 第一筆: {data[0]}")
            
            # 查找上櫃股票是否也包含在內
            tpex_found = []
            for item in data[:100]:  # 只檢查前100筆
                if isinstance(item, dict) and 'Code' in item:
                    code = item.get('Code', '')
                    if code.startswith(('6', '4', '8')):  # 上櫃常見代號開頭
                        tpex_found.append(code)
                        
            if tpex_found:
                logger.info(f"🎯 可能包含上櫃股票: {tpex_found[:5]}")
                
        return data
        
    except Exception as e:
        logger.error(f"❌ TWSE OpenAPI 失敗: {e}")
        return None

def test_twse_mi_index():
    """測試 TWSE MI_INDEX 全市場"""
    
    logger.info("🧪 測試 TWSE MI_INDEX 全市場數據")
    
    url = "https://www.twse.com.tw/exchangeReport/MI_INDEX"
    params = {
        'response': 'json',
        'type': 'ALL'
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"✅ TWSE MI_INDEX 成功")
        logger.info(f"📊 鍵值: {list(data.keys())}")
        logger.info(f"📊 stat: {data.get('stat')}")
        
        if 'data9' in data:
            data9 = data['data9']
            logger.info(f"📊 data9 筆數: {len(data9)}")
            
            # 查看是否有上櫃股票
            tpex_codes = []
            for item in data9[:20]:
                if len(item) > 0:
                    code = str(item[0])
                    if code.startswith(('6', '4', '8')):
                        tpex_codes.append(code)
                        
            if tpex_codes:
                logger.info(f"🎯 MI_INDEX 包含上櫃股票: {tpex_codes}")
                return data
                
        return data
        
    except Exception as e:
        logger.error(f"❌ TWSE MI_INDEX 失敗: {e}")
        return None

def test_tpex_weekly():
    """測試 TPEx 週報數據"""
    
    logger.info("🧪 測試 TPEx 週報數據")
    
    url = "https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/stk_wn1430_result.php"
    params = {
        'l': 'zh-tw',
        'o': 'json'
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"✅ TPEx 週報成功")
        logger.info(f"📊 鍵值: {list(data.keys())}")
        logger.info(f"📊 stat: {data.get('stat')}")
        
        return data
        
    except Exception as e:
        logger.error(f"❌ TPEx 週報失敗: {e}")
        return None

def test_finmind_alternative():
    """測試 FinMind 作為備援"""
    
    logger.info("🧪 測試 FinMind 備援方案")
    
    # FinMind 免費 API
    url = "https://api.finmindtrade.com/api/v4/data"
    params = {
        'dataset': 'TaiwanStockPrice',
        'data_id': '6488',
        'start_date': '2024-07-01',
        'end_date': '2024-07-31'
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"✅ FinMind 成功")
        logger.info(f"📊 鍵值: {list(data.keys())}")
        
        if 'data' in data:
            finmind_data = data['data']
            logger.info(f"📊 FinMind 數據筆數: {len(finmind_data)}")
            
            if finmind_data:
                logger.info(f"📋 第一筆: {finmind_data[0]}")
                logger.info(f"📋 最後一筆: {finmind_data[-1]}")
                
        return data
        
    except Exception as e:
        logger.error(f"❌ FinMind 失敗: {e}")
        return None

def create_ultimate_tpex_solution():
    """創建終極 TPEx 解決方案"""
    
    logger.info("\n" + "=" * 60)
    logger.info("🎯 創建終極 TPEx 解決方案")
    logger.info("=" * 60)
    
    # 策略優先順序
    strategies = [
        {
            "name": "FinMind 備援",
            "test_func": test_finmind_alternative,
            "pros": "穩定、有歷史數據、免費",
            "cons": "需要註冊、有限額"
        },
        {
            "name": "TWSE MI_INDEX 全市場",
            "test_func": test_twse_mi_index,
            "pros": "官方、包含上櫃股票、即時",
            "cons": "只有當日數據"
        },
        {
            "name": "TWSE OpenAPI",
            "test_func": test_twse_all_market,
            "pros": "官方開放 API、穩定",
            "cons": "可能不包含上櫃"
        }
    ]
    
    working_solutions = []
    
    for strategy in strategies:
        logger.info(f"\n🧪 測試策略: {strategy['name']}")
        logger.info(f"💪 優點: {strategy['pros']}")
        logger.info(f"⚠️ 缺點: {strategy['cons']}")
        
        result = strategy['test_func']()
        if result:
            working_solutions.append({
                'strategy': strategy,
                'result': result
            })
            logger.info(f"✅ {strategy['name']} 可用!")
        else:
            logger.warning(f"❌ {strategy['name']} 不可用")
    
    return working_solutions

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 測試 TPEx 替代方案")
    print("=" * 60)
    
    solutions = create_ultimate_tpex_solution()
    
    print("\n" + "=" * 60)
    print("📊 解決方案總結")
    print("=" * 60)
    
    if solutions:
        logger.info(f"✅ 找到 {len(solutions)} 個可用解決方案:")
        for i, sol in enumerate(solutions, 1):
            strategy = sol['strategy']
            logger.info(f"{i}. {strategy['name']}")
            logger.info(f"   {strategy['pros']}")
    else:
        logger.error("❌ 所有方案都失敗了!")
        
    # 推薦最佳方案
    if solutions:
        best = solutions[0]
        logger.info(f"\n🏆 推薦使用: {best['strategy']['name']}")
        logger.info(f"立即實施此方案修復 TPEx 問題!")