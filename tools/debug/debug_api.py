#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
調試TWSE API響應
"""

import requests
import json
from pprint import pprint

def debug_twse_api():
    url = "https://www.twse.com.tw/exchangeReport/STOCK_DAY_ALL"
    params = {
        'response': 'json',
        'date': '20250906'  # 週五
    }
    
    response = requests.get(url, params=params, timeout=30)
    print(f"Status Code: {response.status_code}")
    print(f"Headers: {response.headers}")
    
    try:
        data = response.json()
        print("\nAPI響應結構:")
        print(f"Keys: {list(data.keys())}")
        
        if 'stat' in data:
            print(f"Status: {data['stat']}")
        if 'date' in data:
            print(f"Date: {data['date']}")
        if 'title' in data:
            print(f"Title: {data['title']}")
        if 'fields' in data:
            print(f"Fields: {data['fields']}")
        if 'data' in data:
            print(f"Data records: {len(data['data'])}")
            if data['data']:
                print("First record:")
                pprint(data['data'][0])
                
    except Exception as e:
        print(f"JSON解析錯誤: {e}")
        print("原始回應內容:")
        print(response.text[:500])

if __name__ == "__main__":
    debug_twse_api()