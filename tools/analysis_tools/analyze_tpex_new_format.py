#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析 TPEx 新數據格式
"""

import requests
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def analyze_tpex_new_format():
    """分析新的 TPEx 數據格式"""
    
    url = "https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php"
    params = {
        'l': 'zh-tw',
        'o': 'json',
        'd': '113/07',  # 2024年7月
        'stkno': '6488'
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        logger.info("🔍 分析 TPEx 新格式...")
        
        # 基本結構
        logger.info(f"📊 頂級鍵值: {list(data.keys())}")
        logger.info(f"📊 stat: {data.get('stat')}")
        logger.info(f"📊 date: {data.get('date')}")
        
        if 'tables' in data and len(data['tables']) > 0:
            table = data['tables'][0]
            logger.info(f"📊 table 鍵值: {list(table.keys())}")
            logger.info(f"📊 title: {table.get('title')}")
            logger.info(f"📊 date: {table.get('date')}")
            
            if 'fields' in table:
                fields = table['fields']
                logger.info(f"📊 欄位數量: {len(fields)}")
                logger.info(f"📊 欄位清單: {fields}")
                
            if 'data' in table:
                data_rows = table['data']
                logger.info(f"📊 數據筆數: {len(data_rows)}")
                
                # 查找 6488 的數據
                for i, row in enumerate(data_rows):
                    if len(row) > 0 and '6488' in str(row[0]):
                        logger.info(f"🎯 找到 6488 在第 {i} 行: {row}")
                        
                        # 分析這一行的數據結構
                        if len(row) >= len(fields):
                            logger.info(f"📋 6488 數據解析:")
                            for j, (field, value) in enumerate(zip(fields, row)):
                                logger.info(f"  [{j}] {field}: {value}")
                        break
                else:
                    logger.warning("❌ 未找到 6488 數據")
                    logger.info("📋 前5行數據示例:")
                    for i, row in enumerate(data_rows[:5]):
                        logger.info(f"  [{i}] {row[:3]}...")  # 只顯示前3個欄位
                        
        return data
        
    except Exception as e:
        logger.error(f"❌ 分析失敗: {e}")
        return None

def find_tpex_individual_api():
    """尋找 TPEx 個股歷史數據 API"""
    
    logger.info("🔍 尋找個股歷史數據 API...")
    
    # 測試可能的端點
    test_urls = [
        # 原始端點（已知失效）
        "https://www.tpex.org.tw/web/stock/historical_trading/stk_quote_download.php",
        
        # 可能的新端點
        "https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php",
        "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes",
        "https://www.tpex.org.tw/web/stock/historical/trading_info/stock_quote_download.php",
        
        # 更通用的查詢方式
        "https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/st43_result.php",
    ]
    
    for url in test_urls:
        logger.info(f"\n📡 測試端點: {url}")
        
        # 測試不同的參數組合
        param_sets = [
            {'l': 'zh-tw', 'o': 'json', 'd': '113/07', 'stkno': '6488'},
            {'l': 'zh-tw', 'd': '113/07', 'stkno': '6488'},
            {'date': '20240701', 'stockNo': '6488'},
            {'stkno': '6488', 'date': '113/07'},
        ]
        
        for params in param_sets:
            try:
                response = requests.get(url, params=params, timeout=10)
                
                content_type = response.headers.get('content-type', '')
                logger.info(f"  ✅ {response.status_code} - {content_type} - {len(response.text)} chars")
                
                if response.status_code == 200:
                    if 'json' in content_type:
                        try:
                            data = response.json()
                            if data.get('stat') == 'ok' or data.get('stat') == 'OK':
                                logger.info(f"    🎯 JSON 成功! 參數: {params}")
                                return url, params
                        except:
                            pass
                    elif 'csv' in content_type or 'text' in content_type:
                        if not response.text.startswith('<!DOCTYPE'):
                            logger.info(f"    🎯 可能的 CSV! 參數: {params}")
                            logger.info(f"    前100字: {response.text[:100]}")
                            
            except Exception as e:
                logger.debug(f"  ❌ 失敗: {e}")
                continue
    
    return None, None

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 分析 TPEx 新數據格式")
    print("=" * 60)
    
    # 1. 分析當前可用的格式
    data = analyze_tpex_new_format()
    
    print("\n" + "=" * 60)
    print("🔍 尋找個股歷史 API")
    print("=" * 60)
    
    # 2. 尋找個股歷史數據 API
    working_url, working_params = find_tpex_individual_api()
    
    if working_url:
        print(f"🎯 找到可用端點: {working_url}")
        print(f"🎯 參數: {working_params}")
    else:
        print("❌ 未找到可用的個股歷史數據端點")