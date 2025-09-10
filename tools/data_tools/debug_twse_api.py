#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
調試 TWSE API 回應格式
"""

import requests
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def debug_twse_api(stock_id="2330", year=2024, month=8):
    """調試 TWSE API 實際回應"""
    
    url = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
    params = {
        'response': 'json',
        'date': f"{year}{month:02d}01",
        'stockNo': stock_id
    }
    
    logger.info(f"🔍 測試 TWSE API: {stock_id} {year}/{month}")
    logger.info(f"📡 URL: {url}")
    logger.info(f"📝 參數: {params}")
    
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        
        logger.info(f"✅ API 回應狀態: {data.get('stat', 'Unknown')}")
        logger.info(f"📄 可用鍵值: {list(data.keys())}")
        
        if 'fields' in data:
            logger.info(f"🏷️  欄位名稱: {data['fields']}")
        
        if 'data' in data and data['data']:
            logger.info(f"📊 資料筆數: {len(data['data'])}")
            logger.info(f"📋 第一筆資料: {data['data'][0]}")
            logger.info(f"📋 最後一筆資料: {data['data'][-1]}")
        else:
            logger.warning("❌ 無資料返回")
            
        # 完整回應內容（前200字）
        response_text = json.dumps(data, ensure_ascii=False, indent=2)
        logger.info(f"📄 完整回應 (前300字): {response_text[:300]}...")
        
        return data
        
    except Exception as e:
        logger.error(f"❌ API 請求失敗: {e}")
        return None

if __name__ == "__main__":
    # 測試台積電最近幾個月
    for month in [8, 7, 6]:
        print("=" * 60)
        debug_twse_api("2330", 2024, month)
        print()