#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
尋找真正的 TPEx 歷史數據 API
"""

import requests
import json
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_tpex_historical_apis():
    """測試各種 TPEx 歷史數據 API"""
    
    stock_id = "6488"
    year = 2024
    month = 7
    roc_year = year - 1911
    
    # 可能的歷史數據端點
    test_configs = [
        {
            "name": "個股日成交資訊 (原API)",
            "url": "https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php",
            "params": {
                'l': 'zh-tw',
                'o': 'json',
                'd': f'{roc_year}/{month:02d}',
                'stkno': stock_id
            }
        },
        {
            "name": "個股月成交資訊",
            "url": "https://www.tpex.org.tw/web/stock/aftertrading/monthly_close_quotes/stk_quote_result.php",
            "params": {
                'l': 'zh-tw', 
                'o': 'json',
                'd': f'{roc_year}/{month:02d}',
                'stkno': stock_id
            }
        },
        {
            "name": "個股歷史交易資訊 v1",
            "url": "https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/st43_result.php",
            "params": {
                'l': 'zh-tw',
                'o': 'json', 
                'd': f'{roc_year}/{month:02d}',
                'stkno': stock_id
            }
        },
        {
            "name": "個股歷史交易資訊 v2",
            "url": "https://www.tpex.org.tw/web/stock/historical_trading/stk_quote_result.php",
            "params": {
                'l': 'zh-tw',
                'o': 'json',
                'd': f'{roc_year}/{month:02d}',
                'stkno': stock_id
            }
        },
        {
            "name": "個股每日成交資訊",
            "url": "https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote.php",
            "params": {
                'l': 'zh-tw',
                'd': f'{roc_year}/{month:02d}',
                'stkno': stock_id
            }
        }
    ]
    
    working_apis = []
    
    for config in test_configs:
        logger.info(f"\n🧪 測試: {config['name']}")
        logger.info(f"📡 URL: {config['url']}")
        logger.info(f"📝 參數: {config['params']}")
        
        try:
            response = requests.get(config['url'], params=config['params'], timeout=10)
            
            logger.info(f"📄 狀態: {response.status_code}")
            logger.info(f"📄 類型: {response.headers.get('content-type', 'Unknown')}")
            logger.info(f"📄 長度: {len(response.text)} chars")
            
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '')
                
                if 'json' in content_type:
                    try:
                        data = response.json()
                        
                        # 分析 JSON 結構
                        logger.info(f"📊 JSON 鍵值: {list(data.keys())}")
                        logger.info(f"📊 stat: {data.get('stat')}")
                        
                        # 檢查是否有歷史數據結構
                        has_data = False
                        data_count = 0
                        
                        if 'aaData' in data and data['aaData']:
                            has_data = True
                            data_count = len(data['aaData'])
                            logger.info(f"✅ 找到 aaData: {data_count} 筆")
                            logger.info(f"📋 第一筆: {data['aaData'][0]}")
                            
                        elif 'tables' in data and data['tables']:
                            table = data['tables'][0]
                            if 'data' in table:
                                # 檢查是否是歷史數據還是當日數據
                                table_data = table['data']
                                if len(table_data) > 50:  # 很多筆可能是全市場當日
                                    logger.info(f"⚠️ 可能是全市場當日數據: {len(table_data)} 筆")
                                else:
                                    has_data = True
                                    data_count = len(table_data)
                                    logger.info(f"✅ 找到 tables 數據: {data_count} 筆")
                        
                        if has_data:
                            working_apis.append({
                                'config': config,
                                'data_count': data_count,
                                'response': data
                            })
                            
                    except json.JSONDecodeError:
                        logger.warning(f"❌ JSON 解析失敗")
                        logger.info(f"📄 前100字: {response.text[:100]}")
                        
                elif 'csv' in content_type or 'text' in content_type:
                    if not response.text.startswith('<!DOCTYPE'):
                        logger.info(f"✅ 可能的 CSV 數據")
                        lines = response.text.strip().split('\n')
                        logger.info(f"📄 行數: {len(lines)}")
                        logger.info(f"📋 第一行: {lines[0] if lines else 'Empty'}")
                        
                        working_apis.append({
                            'config': config,
                            'data_count': len(lines),
                            'response': response.text
                        })
                    else:
                        logger.warning(f"❌ 返回 HTML 頁面")
                
        except Exception as e:
            logger.warning(f"❌ 請求失敗: {e}")
            
    return working_apis

def try_alternative_approach():
    """嘗試替代方案：使用 TWSE/TPEx OpenAPI"""
    
    logger.info("\n🔍 嘗試替代方案...")
    
    # 政府開放資料
    alternative_urls = [
        "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL",
        "https://www.twse.com.tw/exchangeReport/MI_INDEX?response=json&type=ALL",
        "https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/stk_wn1430_result.php?l=zh-tw&o=json",
    ]
    
    for url in alternative_urls:
        logger.info(f"\n📡 測試替代端點: {url}")
        
        try:
            response = requests.get(url, timeout=10)
            logger.info(f"📄 狀態: {response.status_code}, 長度: {len(response.text)}")
            
            if response.status_code == 200 and len(response.text) > 100:
                content_type = response.headers.get('content-type', '')
                logger.info(f"✅ 可能可用: {content_type}")
                
        except Exception as e:
            logger.warning(f"❌ 失敗: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("🔍 尋找真正的 TPEx 歷史數據 API")
    print("=" * 60)
    
    working_apis = test_tpex_historical_apis()
    
    print("\n" + "=" * 60)
    print("📊 可用 API 總結")
    print("=" * 60)
    
    if working_apis:
        logger.info(f"✅ 找到 {len(working_apis)} 個可用 API:")
        for i, api in enumerate(working_apis, 1):
            config = api['config']
            logger.info(f"{i}. {config['name']}: {api['data_count']} 筆數據")
            logger.info(f"   URL: {config['url']}")
    else:
        logger.warning("❌ 未找到可用的歷史數據 API")
        
        print("\n" + "=" * 60)
        print("🔍 測試替代方案")
        print("=" * 60)
        try_alternative_approach()