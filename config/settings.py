#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系統配置管理
"""

import os

# 資料庫配置
DATABASE_CONFIG = {
    'path': 'data/cleaned/taiwan_stocks_cleaned.db',
    'backup_path': 'data/backup/',
    'pragma_settings': {
        'journal_mode': 'WAL',
        'synchronous': 'NORMAL',
        'cache_size': 200000,  # 200MB
        'mmap_size': 268435456,  # 256MB
        'temp_store': 'MEMORY'
    }
}

# API配置
API_CONFIG = {
    'twse': {
        'base_url': 'https://www.twse.com.tw/exchangeReport',
        'rate_limit': 6,  # requests per second
        'timeout': 30,
        'retry_attempts': 3
    },
    'finmind': {
        'base_url': 'https://api.finmindtrade.com/api/v4',
        'rate_limit': 10,
        'timeout': 30
    }
}

# N-pattern檢測配置
PATTERN_CONFIG = {
    'min_leg_pct': 0.06,  # 6% 最小腿部變化
    'max_days_ab': 10,    # AB段最大天數
    'max_days_bc': 5,     # BC段最大天數
    'min_volume_ratio': 0.8,  # 最小成交量比率
    'atr_length': 14,     # ATR計算期間
    'atr_multiplier': 0.8 # ATR乘數
}

# 系統配置
SYSTEM_CONFIG = {
    'default_max_stocks': 1900,  # 全市場台股數量
    'test_max_stocks': 500,      # 測試用股票數量
    'max_workers': 4,     # 最大並行工作數
    'chunk_size': 20,     # 批次處理大小
    'log_level': 'INFO',  # 日誌級別
    'enable_cache': True, # 是否啟用快取
    'export_format': 'csv' # 預設匯出格式
}

# 路徑配置
PATHS = {
    'data': 'data',
    'exports': 'data/exports',
    'logs': 'logs',
    'temp': 'temp'
}

def get_absolute_path(relative_path: str) -> str:
    """取得絕對路徑"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, relative_path)

def get_database_path() -> str:
    """取得資料庫絕對路徑"""
    return get_absolute_path(DATABASE_CONFIG['path'])