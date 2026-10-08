"""
create_db.py
建立 orders.db 資料庫，包含 customer, product, orders, order_item 四張資料表，
並寫入繁體中文測試資料與約束條件驗證。
"""

import os
import sqlite3
import sys

# 確保 Windows 終端機正確輸出 UTF-8 中文字元
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "orders.db")


def create_database():
    # 若舊資料庫存在可重新建立確保乾淨狀態
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
        print(f"[*] 移除舊有資料庫檔案: {DB_FILE}")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # 啟用外鍵支援 (SQLite 預設為關閉)
    cursor.execute("PRAGMA foreign_keys = ON;")

    print("[*] 正在建立資料表結構...")

    # 1. 客戶資料表
    cursor.execute("""
    CREATE TABLE customer (
        customer_id  TEXT PRIMARY KEY,                  -- 客戶編號 PK
        name         TEXT NOT NULL,                     -- 名稱
        phone        TEXT,                              -- 電話
        address      TEXT,                              -- 地址
        created_date TEXT NOT NULL                      -- 建檔日期
    );
    """)

    # 2. 商品資料表
    cursor.execute("""
    CREATE TABLE product (
        product_id  TEXT PRIMARY KEY,                   -- 商品編號 PK
        name        TEXT NOT NULL,                      -- 名稱
        unit_price  REAL NOT NULL CHECK (unit_price >= 0), -- 單價 (不可為負)
        stock       INTEGER NOT NULL CHECK (stock >= 0),   -- 庫存 (不可為負)
        category    TEXT                                -- 分類
    );
    """)

    # 3. 訂單資料表
    cursor.execute("""
    CREATE TABLE orders (
        order_id     TEXT PRIMARY KEY,                  -- 訂單編號 PK
        customer_id  TEXT NOT NULL,                     -- 客戶編號 FK
        order_date   TEXT NOT NULL,                     -- 訂單日期
        status       TEXT NOT NULL,                     -- 狀態
        sales_rep    TEXT,                              -- 業務人員
        FOREIGN KEY (customer_id) REFERENCES customer(customer_id)
            ON UPDATE CASCADE ON DELETE RESTRICT
    );
    """)

    # 4. 訂單明細資料表 (以訂單編號 + 商品編號為複合主鍵)
    cursor.execute("""
    CREATE TABLE order_item (
        order_id    TEXT NOT NULL,                      -- 訂單編號 FK
        product_id  TEXT NOT NULL,                      -- 商品編號 FK
        quantity    INTEGER NOT NULL CHECK (quantity > 0),   -- 數量 (必須大於 0)
        unit_price  REAL NOT NULL CHECK (unit_price >= 0),   -- 單價 (下單當時價格，不可為負)
        PRIMARY KEY (order_id, product_id),             -- 複合主鍵
        FOREIGN KEY (order_id) REFERENCES orders(order_id)
            ON UPDATE CASCADE ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES product(product_id)
            ON UPDATE CASCADE ON DELETE RESTRICT
    );
    """)

    print("[*] 資料表建立完成，正在插入測試資料...")

    # 插入客戶資料 (5 筆)
    customers = [
        ("C001", "王小明", "0912-345-678", "台北市中正區重慶南路一段100號", "2026-01-15"),
        ("C002", "林雅筑", "0928-112-233", "新北市板橋區文化路二段50號", "2026-02-01"),
        ("C003", "陳俊豪", "0935-445-566", "台中市西屯區台灣大道三段99號", "2026-02-18"),
        ("C004", "張欣恬", "0956-778-899", "台南市東區中華東路一段20號", "2026-03-05"),
        ("C005", "黃柏彥", "0972-889-900", "高雄市苓雅區四維三路2號", "2026-03-20"),
    ]
    cursor.executemany(
        "INSERT INTO customer (customer_id, name, phone, address, created_date) VALUES (?, ?, ?, ?, ?)",
        customers,
    )

    # 插入商品資料 (5 筆)
    products = [
        ("P001", "輕量無線降噪耳機", 3200, 50, "3C電子"),
        ("P002", "人體工學機械式鍵盤", 2800, 35, "電腦周邊"),
        ("P003", "智能多功能氣炸鍋", 4500, 20, "廚房家電"),
        ("P004", "高磅數防潑水雙肩後背包", 1280, 80, "生活配件"),
        ("P005", "不鏽鋼雙層真空保溫杯", 650, 120, "生活居家"),
    ]
    cursor.executemany(
        "INSERT INTO product (product_id, name, unit_price, stock, category) VALUES (?, ?, ?, ?, ?)",
        products,
    )

    # 插入訂單資料 (5 筆)
    orders = [
        ("ORD20260301", "C001", "2026-03-01 10:15:00", "已完成", "李佩玲"),
        ("ORD20260302", "C002", "2026-03-02 14:30:00", "運送中", "張育誠"),
        ("ORD20260303", "C003", "2026-03-05 09:45:00", "處理中", "李佩玲"),
        ("ORD20260304", "C004", "2026-03-08 16:20:00", "已完成", "趙家豪"),
        ("ORD20260305", "C005", "2026-03-10 11:00:00", "已出貨", "張育誠"),
    ]
    cursor.executemany(
        "INSERT INTO orders (order_id, customer_id, order_date, status, sales_rep) VALUES (?, ?, ?, ?, ?)",
        orders,
    )

    # 插入訂單明細資料 (含多項商品訂單案例、保存下單當時價格)
    order_items = [
        # ORD20260301 (多項商品案例：購買 P001、P002)
        ("ORD20260301", "P001", 1, 3200.0),
        ("ORD20260301", "P002", 1, 2800.0),
        # ORD20260302 (多項商品案例：購買 P003、P005)
        ("ORD20260302", "P003", 1, 4500.0),
        ("ORD20260302", "P005", 2, 650.0),
        # ORD20260303 (單項商品案例)
        ("ORD20260303", "P004", 2, 1280.0),
        # ORD20260304 (多項商品案例：保存下單當時特價 3000，原牌價為 3200)
        ("ORD20260304", "P001", 1, 3000.0),
        ("ORD20260304", "P005", 3, 650.0),
        # ORD20260305 (單項商品案例)
        ("ORD20260305", "P002", 2, 2800.0),
    ]
    cursor.executemany(
        "INSERT INTO order_item (order_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
        order_items,
    )

    conn.commit()
    print("[+] 測試資料插入成功！")

    # 約束驗證測試
    print("[*] 正在驗證 CHECK 與複合主鍵約束條件...")
    test_constraints(cursor)

    conn.close()
    print(f"[+] 資料庫建立完成：{DB_FILE}")


def test_constraints(cursor):
    """驗證資料庫約束條件是否確實生效"""
    # 測試 1: 數量 <= 0 應被阻擋
    try:
        cursor.execute("INSERT INTO order_item (order_id, product_id, quantity, unit_price) VALUES ('ORD20260303', 'P001', 0, 100);")
        print("[-] 警告: 數量 <= 0 未被阻擋！")
    except sqlite3.IntegrityError:
        print("  [OK] CHECK (quantity > 0) 約束驗證通過（成功阻擋數量 <= 0）")

    # 測試 2: 單價 < 0 應被阻擋
    try:
        cursor.execute("INSERT INTO order_item (order_id, product_id, quantity, unit_price) VALUES ('ORD20260303', 'P001', 1, -50);")
        print("[-] 警告: 單價 < 0 未被阻擋！")
    except sqlite3.IntegrityError:
        print("  [OK] CHECK (unit_price >= 0) 約束驗證通過（成功阻擋負數單價）")

    # 測試 3: 複合主鍵重複應被阻擋
    try:
        cursor.execute("INSERT INTO order_item (order_id, product_id, quantity, unit_price) VALUES ('ORD20260301', 'P001', 2, 3200);")
        print("[-] 警告: 複合主鍵重複未被阻擋！")
    except sqlite3.IntegrityError:
        print("  [OK] PRIMARY KEY (order_id, product_id) 複合主鍵約束驗證通過（成功阻擋重複品項）")


if __name__ == "__main__":
    create_database()
