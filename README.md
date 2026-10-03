# Flask Hello World 一頁式網站

這是一個使用 Python Flask 網站框架開發的輕量型 Hello World 一頁式網站。

## 專案結構

- `app.py`：Flask 後端核心邏輯與路由處理。
- `templates/index.html`：現代化、美觀且具備互動性的單頁式 HTML 前端模板。
- `requirements.txt`：Python 依賴套件清單。
- `run.bat`：Windows 專用一鍵啟動腳本。

## 啟動方式

首次執行前，請先安裝依賴套件：

```powershell
python -m pip install -r requirements.txt
```

若使用本機 Anaconda 環境，請改用：

```powershell
& "C:\SoftWare\Anaconda\python.exe" -m pip install -r requirements.txt
```

### 方法一：直接點擊執行
雙擊執行資料夾中的 `run.bat`。

### 方法二：透過命令列執行
在終端機進入此目錄後執行：
```powershell
& "C:\SoftWare\Anaconda\python.exe" app.py
```
或（若已設定好系統 Python 環境變數）：
```powershell
python app.py
```

啟動後請使用瀏覽器開啟：`http://127.0.0.1:5000`

首頁會顯示 Hello, World! 與伺服器時間；點擊「與後端互動打招呼」可取得 Flask API 的問候。於終端機按 `Ctrl+C` 可停止伺服器。
