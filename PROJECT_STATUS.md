# 台股 N 字回撤掃描器 - 專案狀態

## 📁 專案結構 (重新整理完成)

```
台股N字回撤掃描器/
├── main.py                     # 主程式進入點 ✅
├── README.md                   # 專案說明 ✅
├── src/                        # 核心程式碼
│   ├── data/                   # 數據處理模組
│   │   ├── taiwan_stock_pipeline_fixed.py  # 最終版數據管道 ✅
│   │   └── clean_stock_universe.py         # 股票宇宙清理工具 ✅
│   ├── utils/                  # 工具函數
│   │   ├── export_stock_list.py           # 清單導出工具 ✅
│   │   └── data_validation.py             # 數據驗證工具 ✅
│   ├── api/                    # API 服務 (準備開發)
│   └── tests/                  # 測試程式 (準備開發)
├── docs/                       # 文檔
│   ├── PRD.md                  # 產品需求文檔 ✅
│   ├── DATA_SOURCE_REPORT.md   # 數據源驗證報告 ✅
│   └── CLAUDE.md               # 技術規格文檔 ✅
├── data/                       # 數據檔案
│   ├── cleaned/                # 清理後的數據 (生產使用)
│   │   ├── universe_cleaned_20250908.csv   # 最終股票清單 ✅
│   │   └── taiwan_stocks_cleaned.db        # 清理後資料庫 ✅
│   ├── raw/                    # 原始數據
│   └── reports/                # 報告檔案
├── scripts/                    # 開發和測試腳本
│   ├── data_pipeline.py        # 舊版數據管道
│   ├── taiwan_stock_pipeline_optimized.py # 優化版測試
│   └── debug_isin.py           # 調試工具
└── archive/                    # 暫存檔案
    └── *.db, *.csv             # 開發過程中的暫存檔案
```

## ✅ Phase 1 完成狀態

### 數據源驗證 ✅
- [x] TWSE 上市股票清單 (ISIN)
- [x] TPEx 上櫃股票清單 (ISIN) 
- [x] 多重備援機制 (FinMind)
- [x] 數據品質檢查
- [x] 權證和非股票過濾

### 股票宇宙建構 ✅
- [x] **最終清單**: 1,902 檔純股票
  - 上市 (TWSE): 1,046 檔
  - 上櫃 (TPEx): 856 檔
- [x] 嚴格過濾規則 (排除 293 檔權證/ETF)
- [x] 資料庫存儲 (SQLite)
- [x] CSV 格式導出

### 資料品質保證 ✅
- [x] 重複檢查
- [x] 格式驗證 (4位數代號)
- [x] 知名股票確認 (台積電、鴻海等)
- [x] 市場分布合理性檢查

## 🚀 已可開始下一階段

### 核心數據資產
1. **生產用股票清單**: `data/cleaned/universe_cleaned_20250908.csv`
2. **資料庫**: `data/cleaned/taiwan_stocks_cleaned.db` 
3. **數據管道**: `src/data/taiwan_stock_pipeline_fixed.py`

### 執行方式
```bash
# 執行主程式 (數據更新)
python3 main.py

# 單獨執行數據管道
python3 src/data/taiwan_stock_pipeline_fixed.py --update-universe --generate-report
```

## 📋 接下來的開發階段

### Phase 2: N 字回撤算法 (準備開始)
- [ ] ZigZag 轉折點識別
- [ ] ABC 形態檢測
- [ ] 觸發條件判斷
- [ ] 評分系統實作
- [ ] 參數化配置

### Phase 3: API 服務開發
- [ ] FastAPI 框架搭建
- [ ] 掃描 API 端點
- [ ] 股票數據 API
- [ ] 錯誤處理和限流

### Phase 4: 前端界面開發  
- [ ] React 應用框架
- [ ] 參數設置界面
- [ ] 結果展示表格
- [ ] K 線圖整合

### Phase 5: 系統整合與測試
- [ ] 端對端測試
- [ ] 性能優化  
- [ ] Docker 容器化
- [ ] 部署文檔

## 🎯 技術決策記錄

### 數據源策略
- **主要源**: 官方 ISIN 清單 (精確度優先)
- **備援源**: FinMind API (穩定性優先)
- **更新頻率**: 每日 T+1 (符合免費源限制)

### 架構決策
- **後端**: Python + FastAPI + Polars
- **前端**: React + TypeScript + Chart.js
- **資料庫**: SQLite (簡單) + Parquet (效能)
- **部署**: Docker Compose

## ⚠️ 已知問題和限制

1. **TPEx 官方 API**: 部分不穩定，已用 FinMind 補強
2. **FinMind 限制**: 免費版 10,000 次/月
3. **復權處理**: 需在價格數據管道中實作前復權

## 📞 開發準備度

**✅ 可立即開始 Phase 2 開發**
- 數據基礎穩固 (1,902 檔純股票)
- 專案結構清晰
- 程式路徑正確
- 文檔完整

**建議開發順序**:
1. ZigZag 算法實作 → `src/data/zigzag.py`
2. N字形態檢測 → `src/data/pattern_detection.py` 
3. 技術指標計算 → `src/data/indicators.py`
4. 掃描引擎整合 → `src/data/scanner.py`

---

**專案狀態**: 🟢 Phase 1 完成，準備進入 Phase 2  
**最後更新**: 2025-09-08 15:25