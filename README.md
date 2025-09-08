# 台股 N 字回撤掃描器

## 專案結構

```
├── main.py                 # 主程式進入點
├── src/                    # 核心程式碼
│   ├── data/              # 數據處理模組
│   ├── utils/             # 工具函數
│   ├── api/               # API 服務
│   └── tests/             # 測試程式
├── docs/                   # 文檔
├── data/                   # 數據檔案
│   ├── cleaned/           # 清理後的數據
│   ├── raw/               # 原始數據
│   └── reports/           # 報告檔案
├── scripts/               # 開發和測試腳本
└── archive/               # 暫存檔案

## 使用方式

1. 執行數據更新：
```bash
python main.py
```

2. 單獨執行數據管道：
```bash
python src/data/taiwan_stock_pipeline_fixed.py --update-universe --generate-report
```

## 數據源

- **最終股票清單**: `data/cleaned/universe_cleaned_20250908.csv`
- **資料庫**: `data/cleaned/taiwan_stocks_cleaned.db`
- **數據源報告**: `docs/DATA_SOURCE_REPORT.md`

## 開發狀態

- [x] Phase 1: 數據源驗證和股票宇宙建構
- [ ] Phase 2: N 字回撤算法實作
- [ ] Phase 3: API 服務開發  
- [ ] Phase 4: 前端界面開發
- [ ] Phase 5: 系統整合與測試
