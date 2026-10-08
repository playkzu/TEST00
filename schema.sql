-- ====================================================================
-- orders.db 資料庫結構定義 (Schema) 與繁體中文測試資料
-- ====================================================================

PRAGMA foreign_keys = ON;

-- 1. 客戶資料表 (customer)
DROP TABLE IF EXISTS order_item;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS product;
DROP TABLE IF EXISTS customer;

CREATE TABLE customer (
    customer_id  TEXT PRIMARY KEY,                  -- 客戶編號 PK
    name         TEXT NOT NULL,                     -- 名稱
    phone        TEXT,                              -- 電話
    address      TEXT,                              -- 地址
    created_date TEXT NOT NULL                      -- 建檔日期
);

-- 2. 商品資料表 (product)
CREATE TABLE product (
    product_id  TEXT PRIMARY KEY,                   -- 商品編號 PK
    name        TEXT NOT NULL,                      -- 名稱
    unit_price  REAL NOT NULL CHECK (unit_price >= 0), -- 單價 (不可為負)
    stock       INTEGER NOT NULL CHECK (stock >= 0),   -- 庫存 (不可為負)
    category    TEXT                                -- 分類
);

-- 3. 訂單資料表 (orders)
CREATE TABLE orders (
    order_id     TEXT PRIMARY KEY,                  -- 訂單編號 PK
    customer_id  TEXT NOT NULL,                     -- 客戶編號 FK
    order_date   TEXT NOT NULL,                     -- 訂單日期
    status       TEXT NOT NULL,                     -- 狀態
    sales_rep    TEXT,                              -- 業務人員
    FOREIGN KEY (customer_id) REFERENCES customer(customer_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

-- 4. 訂單明細資料表 (order_item)
CREATE TABLE order_item (
    order_id    TEXT NOT NULL,                      -- 訂單編號 FK
    product_id  TEXT NOT NULL,                      -- 商品編號 FK
    quantity    INTEGER NOT NULL CHECK (quantity > 0),   -- 數量 (必須大於 0)
    unit_price  REAL NOT NULL CHECK (unit_price >= 0),   -- 單價 (下單當時價格，不可為負)
    PRIMARY KEY (order_id, product_id),             -- 「訂單編號 + 商品編號」複合主鍵
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES product(product_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

-- ====================================================================
-- 插入繁體中文測試資料 (各 5 筆資料，含單筆訂單購買多項商品之案例)
-- ====================================================================

-- 1. 客戶資料 (5 筆)
INSERT INTO customer (customer_id, name, phone, address, created_date) VALUES
('C001', '王小明', '0912-345-678', '台北市中正區重慶南路一段100號', '2026-01-15'),
('C002', '林雅筑', '0928-112-233', '新北市板橋區文化路二段50號', '2026-02-01'),
('C003', '陳俊豪', '0935-445-566', '台中市西屯區台灣大道三段99號', '2026-02-18'),
('C004', '張欣恬', '0956-778-899', '台南市東區中華東路一段20號', '2026-03-05'),
('C005', '黃柏彥', '0972-889-900', '高雄市苓雅區四維三路2號', '2026-03-20');

-- 2. 商品資料 (5 筆)
INSERT INTO product (product_id, name, unit_price, stock, category) VALUES
('P001', '輕量無線降噪耳機', 3200, 50, '3C電子'),
('P002', '人體工學機械式鍵盤', 2800, 35, '電腦周邊'),
('P003', '智能多功能氣炸鍋', 4500, 20, '廚房家電'),
('P004', '高磅數防潑水雙肩後背包', 1280, 80, '生活配件'),
('P005', '不鏽鋼雙層真空保溫杯', 650, 120, '生活居家');

-- 3. 訂單資料 (5 筆)
INSERT INTO orders (order_id, customer_id, order_date, status, sales_rep) VALUES
('ORD20260301', 'C001', '2026-03-01 10:15:00', '已完成', '李佩玲'),
('ORD20260302', 'C002', '2026-03-02 14:30:00', '運送中', '張育誠'),
('ORD20260303', 'C003', '2026-03-05 09:45:00', '處理中', '李佩玲'),
('ORD20260304', 'C004', '2026-03-08 16:20:00', '已完成', '趙家豪'),
('ORD20260305', 'C005', '2026-03-10 11:00:00', '已出貨', '張育誠');

-- 4. 訂單明細資料 (含多項商品訂單案例、保存下單當下價格)
INSERT INTO order_item (order_id, product_id, quantity, unit_price) VALUES
-- 訂單 ORD20260301 (多項商品案例：購買 P001、P002)
('ORD20260301', 'P001', 1, 3200),
('ORD20260301', 'P002', 1, 2800),

-- 訂單 ORD20260302 (多項商品案例：購買 P003、P005)
('ORD20260302', 'P003', 1, 4500),
('ORD20260302', 'P005', 2, 650),

-- 訂單 ORD20260303 (單項商品案例)
('ORD20260303', 'P004', 2, 1280),

-- 訂單 ORD20260304 (多項商品案例：保存下單當時價格 3000，即便目前牌價為 3200)
('ORD20260304', 'P001', 1, 3000),
('ORD20260304', 'P005', 3, 650),

-- 訂單 ORD20260305 (單項商品案例)
('ORD20260305', 'P002', 2, 2800);
