#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
深度調試 TPEx API 問題
"""

import requests
import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def debug_tpex_json_api(stock_id="6488", year=2024, month=8):
    """調試 TPEx JSON API"""
    
    roc_year = year - 1911
    
    url = "https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php"
    params = {
        'l': 'zh-tw',
        'o': 'json',
        'd': f"{roc_year}/{month:02d}",
        'stkno': stock_id
    }
    
    logger.info(f"🔍 測試 TPEx JSON API: {stock_id} {year}/{month}")
    logger.info(f"📡 URL: {url}")
    logger.info(f"📝 參數: {params}")
    
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        
        logger.info(f"📄 HTTP Status: {response.status_code}")
        logger.info(f"📄 Content-Type: {response.headers.get('content-type', 'Unknown')}")
        logger.info(f"📄 Content-Length: {len(response.text)}")
        
        try:
            data = response.json()
            
            logger.info(f"✅ JSON 解析成功")
            logger.info(f"📄 可用鍵值: {list(data.keys())}")
            logger.info(f"📄 stat: {data.get('stat', 'Missing')}")
            logger.info(f"📄 title: {data.get('title', 'Missing')}")
            
            if 'aaData' in data:
                logger.info(f"📊 aaData 長度: {len(data.get('aaData', []))}")
                if data['aaData']:
                    logger.info(f"📋 第一筆 aaData: {data['aaData'][0]}")
            
            # 完整回應內容（前500字）
            response_text = json.dumps(data, ensure_ascii=False, indent=2)
            logger.info(f"📄 完整回應 (前500字): {response_text[:500]}...")
            
            return data
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON 解析失敗: {e}")
            logger.info(f"📄 原始回應 (前500字): {response.text[:500]}...")
            return None
            
    except Exception as e:
        logger.error(f"❌ HTTP 請求失敗: {e}")
        return None

def debug_tpex_csv_api(stock_id="6488", year=2024, month=8):
    """調試 TPEx CSV API"""
    
    roc_year = year - 1911
    
    url = "https://www.tpex.org.tw/web/stock/historical_trading/stk_quote_download.php"
    params = {
        "l": "zh-tw",
        "d": f"{roc_year}/{month:02d}",
        "stkno": stock_id,
        "download": "csv"
    }
    
    logger.info(f"🔍 測試 TPEx CSV API: {stock_id} {year}/{month}")
    logger.info(f"📡 URL: {url}")
    logger.info(f"📝 參數: {params}")
    
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        
        logger.info(f"📄 HTTP Status: {response.status_code}")
        logger.info(f"📄 Content-Type: {response.headers.get('content-type', 'Unknown')}")
        logger.info(f"📄 Content-Length: {len(response.text)}")
        
        # 檢查前幾行
        lines = response.text.strip().split('\n')[:5]
        logger.info(f"📄 前5行內容:")
        for i, line in enumerate(lines):
            logger.info(f"  [{i}] {line[:100]}...")
        
        return response.text
        
    except Exception as e:
        logger.error(f"❌ CSV 請求失敗: {e}")
        return None

def test_different_stocks():
    """測試不同的上櫃股票"""
    
    # 常見上櫃股票列表
    tpex_stocks = [
        "6488",  # 環球晶
        "3034",  # 聯詠 (但可能已轉上市)
        "4958",  # 臻鼎-KY
        "6415",  # 矽力-KY
        "5269",  # 祥碩
        "6182",  # 合晶
        "3443",  # 創意
        "4966",  # 譜瑞-KY
    ]
    
    logger.info(f"🧪 測試多檔上櫃股票...")
    
    for stock_id in tpex_stocks[:3]:  # 只測前3檔
        logger.info(f"\n{'='*40}")
        logger.info(f"測試 {stock_id}")
        logger.info(f"{'='*40}")
        
        # 測試 JSON API
        json_result = debug_tpex_json_api(stock_id, 2024, 7)
        
        # 如果 JSON 失敗，測試 CSV
        if not json_result or json_result.get('stat') != 'OK':
            logger.info(f"JSON 失敗，測試 CSV...")
            csv_result = debug_tpex_csv_api(stock_id, 2024, 7)

def check_tpex_stock_list():
    """檢查 TPEx 股票清單 API"""
    
    logger.info(f"🔍 檢查 TPEx 股票清單...")
    
    # TPEx 股票清單 API
    url = "https://www.tpex.org.tw/web/stock/aftertrading/stock_info/stk_info_result.php"
    params = {
        'l': 'zh-tw',
        'o': 'json'
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"✅ 股票清單 API 成功")
        logger.info(f"📄 stat: {data.get('stat', 'Missing')}")
        
        if 'aaData' in data:
            stocks = data['aaData']
            logger.info(f"📊 找到 {len(stocks)} 檔股票")
            
            # 查找環球晶
            for stock in stocks:
                if len(stock) > 0 and '6488' in stock[0]:
                    logger.info(f"🎯 找到 6488: {stock}")
                    return True
                    
            # 顯示前5檔
            logger.info(f"📋 前5檔股票:")
            for i, stock in enumerate(stocks[:5]):
                logger.info(f"  {stock}")
            
        return False
        
    except Exception as e:
        logger.error(f"❌ 股票清單 API 失敗: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 TPEx API 深度調試")
    print("=" * 60)
    
    # 1. 檢查股票是否在 TPEx
    check_tpex_stock_list()
    
    print("\n" + "=" * 60)
    print("🧪 測試 JSON API")
    print("=" * 60)
    
    # 2. 測試 JSON API
    debug_tpex_json_api("6488", 2024, 7)
    
    print("\n" + "=" * 60)
    print("🧪 測試 CSV API")
    print("=" * 60)
    
    # 3. 測試 CSV API
    debug_tpex_csv_api("6488", 2024, 7)
    
    print("\n" + "=" * 60)
    print("🧪 測試其他股票")
    print("=" * 60)
    
    # 4. 測試其他股票
    test_different_stocks()