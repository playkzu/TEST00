# 訂單管理系統 (Flask + SQLite + Bootstrap 5)

一個具備現代化 UI、SQLite 交易機制與出貨單 QR Code 生成的全功能訂單管理系統。

---

## 系統特色與架構

### 一、資料表設計 (orders.db)
1. **customer**：`customer_id` (PK)、`name`、`phone`、`address`、`created_date`
2. **product**：`product_id` (PK)、`name`、`unit_price` (CHECK >= 0)、`stock` (CHECK >= 0)、`category`
3. **orders**：`order_id` (PK)、`customer_id` (FK)、`order_date`、`status` (CHECK 狀態限制)、`sales_rep`
4. **order_item**：`order_id` (FK)、`product_id` (FK)、`quantity` (CHECK > 0)、`unit_price` (CHECK >= 0)，以「`order_id + product_id`」為複合主鍵
5. **admin_user**：`username` (PK)、`password_hash`、`display_name`

### 二、核心功能
- **管理員權限**：登入驗證、未登入攔截與 Session 管理。
- **維護功能**：完整支援客戶、商品與訂單之 CRUD 操作。
- **新增訂單**：客戶採下拉選單，商品支援一次勾選多項並即時填寫數量與計算小計總額。
- **單價快照**：`order_item` 保存下單當時價格，後續商品調整牌價不影響歷史訂單。
- **列表直接更新狀態**：訂單列表內可直接切換「處理中 / 已出貨 / 已完成 / 已取消」，即時同步資料庫。
- **專屬出貨單與 QR Code**：每張訂單皆有專屬頁面 `/order/<訂單編號>`，自動生成對應出貨單 QR Code，並支援一鍵列印（自動排版）。
- **繁體中文測試資料**：預設已建立 5 筆客戶、5 筆商品、5 筆訂單與多項商品之訂單明細。

---

## 帳號資訊

- **管理員帳號**：`admin`
- **管理員密碼**：`admin123`

---

## 啟動方式

### 方法一：雙擊執行腳本 (Windows)
雙擊資料夾內的 `run.bat` 即可一鍵啟動伺服器。

### 方法二：命令列啟動
```powershell
cd "antigravity_class"
.\.venv\Scripts\python.exe app.py
```
啟動後在瀏覽器開啟：**http://127.0.0.1:5000**

---

## 自動化測試

執行完整單元與整合測試：
```powershell
cd "antigravity_class"
.\.venv\Scripts\python.exe -m pytest tests -v
```
