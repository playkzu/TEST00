"""
Flask + SQLite + Bootstrap 5 訂單管理系統
進階安全與功能強化：
1. 管理員密碼採 Werkzeug 雜湊儲存（scrypt/pbkdf2），程式與畫面絕無明碼
2. 後台所有頁面需登入 Session 且角色限定為 admin 方可存取
3. 所有 SQL 全數採用參數化查詢（? 佔位符），徹底杜絕 SQL Injection
4. 客戶與商品皆採用下拉選單；訂單編號嚴格實施「SO+數字」格式驗證
5. 數量強制正整數：前端 HTML5/JS、後端 Regex/Int、資料庫 CHECK 三層防護
6. 保留下單當時單價，動態出貨單 QR Code 生成
"""

import base64
import functools
import io
import json
import os
import re
import sqlite3
import sys
from datetime import datetime
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
import qrcode
from werkzeug.security import check_password_hash, generate_password_hash

# 確保輸出支援 UTF-8
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "order-system-secure-key-2026")
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "orders.db")

# 狀態常數 (使用 Unicode 跳脫字元，保證全平台資料庫編碼一致)
STATUS_PENDING = "\u8655\u7406\u4e2d"     # 處理中
STATUS_SHIPPED = "\u5df2\u51fa\u8ca8"     # 已出貨
STATUS_COMPLETED = "\u5df2\u5b8c\u6210"   # 已完成
STATUS_CANCELLED = "\u5df2\u53d6\u6d88"   # 已取消
ALLOWED_STATUSES = [STATUS_PENDING, STATUS_SHIPPED, STATUS_COMPLETED, STATUS_CANCELLED]

# 預設管理員帳號與安全雜湊字串 (程式碼中絕無明碼密碼)
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD_HASH = os.environ.get(
    "ADMIN_PASSWORD_HASH",
    "scrypt:32768:8:1$GRXqZTu7u8EvVCIg$ad2f8d1f2e084b75553e4170d93010ba853e4ad0e2867bd5429d2619f6ede552332d205124987e8e2cb7c185c980de1e9323965565e09f11715cc7dd4332daa3"
)


def get_db():
    """取得資料庫連線並開啟 Row 字典映射與外鍵約束"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    """初始化資料庫結構與預設測試資料 (含三層 CHECK 約束)"""
    conn = get_db()
    cursor = conn.cursor()

    # 1. 客戶資料表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customer (
        customer_id  TEXT PRIMARY KEY,
        name         TEXT NOT NULL,
        phone        TEXT,
        address      TEXT,
        created_date TEXT NOT NULL
    );
    """)

    # 2. 商品資料表 (單價不可為負，庫存為非負整數)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS product (
        product_id  TEXT PRIMARY KEY,
        name        TEXT NOT NULL,
        unit_price  REAL NOT NULL CHECK (unit_price >= 0),
        stock       INTEGER NOT NULL CHECK (typeof(stock) = 'integer' AND stock >= 0),
        category    TEXT
    );
    """)

    # 3. 訂單資料表 (訂單編號第三層 CHECK 約束：必須為 SO 開頭且後接數字)
    status_check_sql = f"CHECK (status IN ('{STATUS_PENDING}', '{STATUS_SHIPPED}', '{STATUS_COMPLETED}', '{STATUS_CANCELLED}'))"
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS orders (
        order_id     TEXT PRIMARY KEY CHECK (order_id GLOB 'SO[0-9]*' AND length(order_id) >= 3),
        customer_id  TEXT NOT NULL,
        order_date   TEXT NOT NULL,
        status       TEXT NOT NULL {status_check_sql},
        sales_rep    TEXT,
        FOREIGN KEY (customer_id) REFERENCES customer(customer_id)
            ON UPDATE CASCADE ON DELETE RESTRICT
    );
    """)

    # 4. 訂單明細資料表 (數量第三層 CHECK 約束：必須為整數型別且嚴格大於 0)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_item (
        order_id    TEXT NOT NULL,
        product_id  TEXT NOT NULL,
        quantity    INTEGER NOT NULL CHECK (typeof(quantity) = 'integer' AND quantity > 0),
        unit_price  REAL NOT NULL CHECK (unit_price >= 0),
        PRIMARY KEY (order_id, product_id),
        FOREIGN KEY (order_id) REFERENCES orders(order_id)
            ON UPDATE CASCADE ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES product(product_id)
            ON UPDATE CASCADE ON DELETE RESTRICT
    );
    """)

    # 5. 管理員帳號資料表 (密碼雜湊儲存，含角色欄位)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admin_user (
        username      TEXT PRIMARY KEY,
        password_hash TEXT NOT NULL,
        display_name  TEXT NOT NULL,
        role          TEXT NOT NULL DEFAULT 'admin'
    );
    """)

    # 檢查並確保預設管理員存在 (以參數化查詢寫入雜湊)
    cursor.execute("SELECT COUNT(*) FROM admin_user WHERE username = ?;", (DEFAULT_ADMIN_USERNAME,))
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO admin_user (username, password_hash, display_name, role) VALUES (?, ?, ?, ?);",
            (DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD_HASH, "系統管理員", "admin"),
        )

    # 檢查並寫入繁體中文測試客戶 (5 筆)
    cursor.execute("SELECT COUNT(*) FROM customer;")
    if cursor.fetchone()[0] == 0:
        customers = [
            ("C001", "王小明", "0912-345-678", "台北市中正區重慶南路一段100號", "2026-01-15"),
            ("C002", "林雅筑", "0928-112-233", "新北市板橋區文化路二段50號", "2026-02-01"),
            ("C003", "陳俊豪", "0935-445-566", "台中市西屯區台灣大道三段99號", "2026-02-18"),
            ("C004", "張欣恬", "0956-778-899", "台南市東區中華東路一段20號", "2026-03-05"),
            ("C005", "黃柏彥", "0972-889-900", "高雄市苓雅區四維三路2號", "2026-03-20"),
        ]
        cursor.executemany(
            "INSERT INTO customer (customer_id, name, phone, address, created_date) VALUES (?, ?, ?, ?, ?);",
            customers,
        )

    # 檢查並寫入繁體中文測試商品 (5 筆)
    cursor.execute("SELECT COUNT(*) FROM product;")
    if cursor.fetchone()[0] == 0:
        products = [
            ("P001", "輕量無線降噪耳機", 3200.0, 50, "3C電子"),
            ("P002", "人體工學機械式鍵盤", 2800.0, 35, "電腦周邊"),
            ("P003", "智能多功能氣炸鍋", 4500.0, 20, "廚房家電"),
            ("P004", "高磅數防潑水雙肩後背包", 1280.0, 80, "生活配件"),
            ("P005", "不鏽鋼雙層真空保溫杯", 650.0, 120, "生活居家"),
        ]
        cursor.executemany(
            "INSERT INTO product (product_id, name, unit_price, stock, category) VALUES (?, ?, ?, ?, ?);",
            products,
        )

    # 檢查並寫入符合 SO+數字 格式之繁體中文測試訂單 (5 筆)
    cursor.execute("SELECT COUNT(*) FROM orders;")
    if cursor.fetchone()[0] == 0:
        orders = [
            ("SO20260301", "C001", "2026-03-01 10:15:00", STATUS_COMPLETED, "李佩玲"),
            ("SO20260302", "C002", "2026-03-02 14:30:00", STATUS_SHIPPED, "張育誠"),
            ("SO20260303", "C003", "2026-03-05 09:45:00", STATUS_PENDING, "李佩玲"),
            ("SO20260304", "C004", "2026-03-08 16:20:00", STATUS_COMPLETED, "趙家豪"),
            ("SO20260305", "C005", "2026-03-10 11:00:00", STATUS_SHIPPED, "張育誠"),
        ]
        cursor.executemany(
            "INSERT INTO orders (order_id, customer_id, order_date, status, sales_rep) VALUES (?, ?, ?, ?, ?);",
            orders,
        )

    # 檢查並寫入測試訂單明細 (含多項商品、正整數數量、保存下單當下價格)
    cursor.execute("SELECT COUNT(*) FROM order_item;")
    if cursor.fetchone()[0] == 0:
        order_items = [
            ("SO20260301", "P001", 1, 3200.0),
            ("SO20260301", "P002", 1, 2800.0),
            ("SO20260302", "P003", 1, 4500.0),
            ("SO20260302", "P005", 2, 650.0),
            ("SO20260303", "P004", 2, 1280.0),
            ("SO20260304", "P001", 1, 3000.0),  # 保存下單當時特價 3000
            ("SO20260304", "P005", 3, 650.0),
            ("SO20260305", "P002", 2, 2800.0),
        ]
        cursor.executemany(
            "INSERT INTO order_item (order_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?);",
            order_items,
        )

    conn.commit()
    conn.close()


# 初始化資料庫結構
init_db()


def admin_required(view):
    """
    後台頁面存取權限驗證裝飾器：
    1. 必須已登入 Session (session['logged_in'] is True)
    2. 角色必須嚴格為管理員 (session['role'] == 'admin')
    """
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if not session.get("logged_in"):
            flash("請先登入管理員帳號以存取後台管理功能。", "warning")
            return redirect(url_for("login", next=request.path))
        if session.get("role") != "admin":
            flash("權限不足：您目前的身份非系統管理員，無法進入後台！", "danger")
            return redirect(url_for("login"))
        return view(**kwargs)
    return wrapped_view


def generate_qr_code_base64(data_text):
    """產生出貨單專屬網址之 QR Code (Base64 PNG)"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=6,
        border=2,
    )
    qr.add_data(data_text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1a252f", back_color="#ffffff")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


# ====================================================================
# 身份認證模組 (Werkzeug 雜湊比對，畫面與程式零明碼)
# ====================================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("logged_in") and session.get("role") == "admin":
        return redirect(url_for("admin"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = get_db()
        cursor = conn.cursor()
        # 參數化查詢查詢管理員帳號
        cursor.execute(
            "SELECT username, password_hash, display_name, role FROM admin_user WHERE username = ?;",
            (username,),
        )
        user = cursor.fetchone()
        conn.close()

        # 使用 werkzeug 安全雜湊比對密碼
        if user and check_password_hash(user["password_hash"], password):
            session["logged_in"] = True
            session["username"] = user["username"]
            session["display_name"] = user["display_name"]
            session["role"] = user["role"]
            flash(f"登入成功！歡迎回來，{user['display_name']}。", "success")
            next_url = request.args.get("next")
            return redirect(next_url or url_for("admin"))
        else:
            flash("帳號或密碼錯誤，請重新確認。", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("您已安全登出後台管理系統。", "info")
    return redirect(url_for("login"))


# ====================================================================
# 營運儀表板 /admin (需 admin 權限，全參數化 SQL)
# ====================================================================

@app.route("/")
def index():
    if session.get("logged_in") and session.get("role") == "admin":
        return redirect(url_for("admin"))
    return redirect(url_for("login"))


@app.route("/admin", endpoint="admin")
@app.route("/admin/dashboard", endpoint="admin_dashboard")
@app.route("/dashboard", endpoint="dashboard")
@admin_required
def admin_dashboard():
    """
    營運儀表板 (/admin):
    1. 上方四張 KPI 卡：累計營收、有效訂單數、平均客單價、客戶數 (已取消訂單不列入計算)
    2. 每月營收趨勢：折線圖 (Chart.js)
    3. 訂單狀態分布：環圈圖 (Chart.js)
    4. 熱銷商品 Top 5：商品名稱、售出數量、營收
    5. 客戶消費排行 Top 5：客戶名稱、訂單數、消費金額
    6. 全額千分位格式化與 Bootstrap 5 響應式排版 (手機單欄顯示)
    """
    conn = get_db()
    cursor = conn.cursor()

    # 1. 上方四張 KPI 卡 (狀態為「已取消」之訂單不列入計算)
    # 1.1 累計營收
    cursor.execute("""
    SELECT COALESCE(SUM(oi.quantity * oi.unit_price), 0)
    FROM order_item oi
    JOIN orders o ON oi.order_id = o.order_id
    WHERE o.status != ?;
    """, (STATUS_CANCELLED,))
    total_revenue = float(cursor.fetchone()[0])

    # 1.2 有效訂單數 (排除已取消)
    cursor.execute("SELECT COUNT(*) FROM orders WHERE status != ?;", (STATUS_CANCELLED,))
    valid_order_count = int(cursor.fetchone()[0])

    # 1.3 平均客單價 (AOV: 累計營收 / 有效訂單數)
    avg_order_value = (total_revenue / valid_order_count) if valid_order_count > 0 else 0.0

    # 1.4 客戶數 (成交客戶數：排除已取消訂單之獨立客戶數；及全系統總客戶數)
    cursor.execute("SELECT COUNT(DISTINCT customer_id) FROM orders WHERE status != ?;", (STATUS_CANCELLED,))
    active_customer_count = int(cursor.fetchone()[0])

    cursor.execute("SELECT COUNT(*) FROM customer;")
    total_customer_count = int(cursor.fetchone()[0])

    # 2. 每月營收趨勢：折線圖 (Chart.js，排除已取消)
    cursor.execute("""
    SELECT strftime('%Y-%m', o.order_date) AS month,
           COALESCE(SUM(oi.quantity * oi.unit_price), 0) AS revenue
    FROM orders o
    JOIN order_item oi ON o.order_id = oi.order_id
    WHERE o.status != ?
    GROUP BY strftime('%Y-%m', o.order_date)
    ORDER BY month ASC;
    """, (STATUS_CANCELLED,))
    monthly_rows = cursor.fetchall()
    monthly_labels = [row["month"] for row in monthly_rows]
    monthly_data = [float(row["revenue"]) for row in monthly_rows]
    if not monthly_labels:
        monthly_labels = [datetime.now().strftime("%Y-%m")]
        monthly_data = [0.0]

    # 3. 訂單狀態分布：環圈圖 (Chart.js，包含全部狀態)
    cursor.execute("""
    SELECT status, COUNT(*) AS count
    FROM orders
    GROUP BY status;
    """)
    status_rows = cursor.fetchall()
    status_dict = {row["status"]: int(row["count"]) for row in status_rows}
    status_order = [STATUS_PENDING, STATUS_SHIPPED, STATUS_COMPLETED, STATUS_CANCELLED]
    status_labels = status_order
    status_data = [status_dict.get(s, 0) for s in status_order]

    # 4. 熱銷商品 Top 5 (排除已取消，依售出數量排序)
    cursor.execute("""
    SELECT p.product_id,
           p.name AS product_name,
           p.category,
           p.unit_price,
           COALESCE(SUM(oi.quantity), 0) AS total_quantity,
           COALESCE(SUM(oi.quantity * oi.unit_price), 0) AS total_revenue
    FROM product p
    JOIN order_item oi ON p.product_id = oi.product_id
    JOIN orders o ON oi.order_id = o.order_id
    WHERE o.status != ?
    GROUP BY p.product_id, p.name, p.category, p.unit_price
    ORDER BY total_quantity DESC, total_revenue DESC
    LIMIT ?;
    """, (STATUS_CANCELLED, 5))
    top_products = cursor.fetchall()

    # 5. 客戶消費排行 Top 5 (排除已取消，依消費金額排序)
    cursor.execute("""
    SELECT c.customer_id,
           c.name AS customer_name,
           c.phone,
           COUNT(DISTINCT o.order_id) AS order_count,
           COALESCE(SUM(oi.quantity * oi.unit_price), 0) AS total_spent
    FROM customer c
    JOIN orders o ON c.customer_id = o.customer_id
    JOIN order_item oi ON o.order_id = oi.order_id
    WHERE o.status != ?
    GROUP BY c.customer_id, c.name, c.phone
    ORDER BY total_spent DESC, order_count DESC
    LIMIT ?;
    """, (STATUS_CANCELLED, 5))
    top_customers = cursor.fetchall()

    # 輔助：低庫存監控商品
    cursor.execute("""
    SELECT product_id, name, unit_price, stock, category 
    FROM product 
    WHERE stock < ? 
    ORDER BY stock ASC
    LIMIT 5;
    """, (30,))
    low_stock_products = cursor.fetchall()

    conn.close()

    return render_template(
        "admin.html",
        total_revenue=total_revenue,
        valid_order_count=valid_order_count,
        avg_order_value=avg_order_value,
        active_customer_count=active_customer_count,
        total_customer_count=total_customer_count,
        monthly_labels_json=json.dumps(monthly_labels),
        monthly_data_json=json.dumps(monthly_data),
        status_labels_json=json.dumps(status_labels),
        status_data_json=json.dumps(status_data),
        top_products=top_products,
        top_customers=top_customers,
        low_stock_products=low_stock_products,
    )


# ====================================================================
# 客戶管理 (需 admin 權限，全參數化 SQL)
# ====================================================================

@app.route("/customers")
@admin_required
def customers():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT c.customer_id, c.name, c.phone, c.address, c.created_date,
           COUNT(o.order_id) AS order_count
    FROM customer c
    LEFT JOIN orders o ON c.customer_id = o.customer_id
    GROUP BY c.customer_id
    ORDER BY c.customer_id ASC;
    """)
    customer_list = cursor.fetchall()
    conn.close()
    return render_template("customers.html", customers=customer_list)


@app.route("/customers/new", methods=["POST"])
@admin_required
def customer_create():
    customer_id = request.form.get("customer_id", "").strip().upper()
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    address = request.form.get("address", "").strip()

    if not customer_id or not name:
        flash("客戶編號與客戶名稱為必填項目！", "danger")
        return redirect(url_for("customers"))

    created_date = datetime.now().strftime("%Y-%m-%d")
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO customer (customer_id, name, phone, address, created_date) VALUES (?, ?, ?, ?, ?);",
            (customer_id, name, phone, address, created_date),
        )
        conn.commit()
        flash(f"客戶「{name}」({customer_id}) 建立成功！", "success")
    except sqlite3.IntegrityError:
        flash(f"客戶編號「{customer_id}」已存在，請使用不同編號。", "danger")
    finally:
        conn.close()

    return redirect(url_for("customers"))


@app.route("/customers/<customer_id>/edit", methods=["POST"])
@admin_required
def customer_update(customer_id):
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    address = request.form.get("address", "").strip()

    if not name:
        flash("客戶名稱為必填項目！", "danger")
        return redirect(url_for("customers"))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE customer SET name = ?, phone = ?, address = ? WHERE customer_id = ?;",
        (name, phone, address, customer_id),
    )
    conn.commit()
    conn.close()
    flash(f"客戶「{name}」資料已更新完成！", "success")
    return redirect(url_for("customers"))


@app.route("/customers/<customer_id>/delete", methods=["POST"])
@admin_required
def customer_delete(customer_id):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM customer WHERE customer_id = ?;", (customer_id,))
        conn.commit()
        flash(f"已刪除客戶 ({customer_id})。", "info")
    except sqlite3.IntegrityError:
        flash(f"無法刪除客戶 ({customer_id})：該客戶已有訂單紀錄！", "danger")
    finally:
        conn.close()
    return redirect(url_for("customers"))


# ====================================================================
# 商品管理 (需 admin 權限，全參數化 SQL，改價不影響歷史訂單)
# ====================================================================

@app.route("/products")
@admin_required
def products():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT p.product_id, p.name, p.unit_price, p.stock, p.category,
           COALESCE(SUM(oi.quantity), 0) AS total_sold
    FROM product p
    LEFT JOIN order_item oi ON p.product_id = oi.product_id
    GROUP BY p.product_id
    ORDER BY p.product_id ASC;
    """)
    product_list = cursor.fetchall()
    conn.close()
    return render_template("products.html", products=product_list)


@app.route("/products/new", methods=["POST"])
@admin_required
def product_create():
    product_id = request.form.get("product_id", "").strip().upper()
    name = request.form.get("name", "").strip()
    category = request.form.get("category", "").strip()
    try:
        unit_price = float(request.form.get("unit_price", 0))
        stock = int(request.form.get("stock", 0))
    except ValueError:
        flash("單價或庫存數值格式錯誤！", "danger")
        return redirect(url_for("products"))

    if unit_price < 0 or stock < 0:
        flash("單價與庫存不可為負數！", "danger")
        return redirect(url_for("products"))

    if not product_id or not name:
        flash("商品編號與名稱為必填欄位！", "danger")
        return redirect(url_for("products"))

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO product (product_id, name, unit_price, stock, category) VALUES (?, ?, ?, ?, ?);",
            (product_id, name, unit_price, stock, category),
        )
        conn.commit()
        flash(f"已成功新增商品「{name}」({product_id})！", "success")
    except sqlite3.IntegrityError:
        flash(f"商品編號「{product_id}」重複或違反約束條件！", "danger")
    finally:
        conn.close()

    return redirect(url_for("products"))


@app.route("/products/<product_id>/edit", methods=["POST"])
@admin_required
def product_update(product_id):
    name = request.form.get("name", "").strip()
    category = request.form.get("category", "").strip()
    try:
        unit_price = float(request.form.get("unit_price", 0))
        stock = int(request.form.get("stock", 0))
    except ValueError:
        flash("單價或庫存數值格式錯誤！", "danger")
        return redirect(url_for("products"))

    if unit_price < 0 or stock < 0:
        flash("單價與庫存不可為負數！", "danger")
        return redirect(url_for("products"))

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE product SET name = ?, unit_price = ?, stock = ?, category = ? WHERE product_id = ?;",
            (name, unit_price, stock, category, product_id),
        )
        conn.commit()
        flash(f"商品「{name}」牌價已變更為 NT$ {unit_price:,.0f}（歷史訂單單價不受影響）。", "success")
    except sqlite3.IntegrityError as e:
        flash(f"更新失敗：{e}", "danger")
    finally:
        conn.close()

    return redirect(url_for("products"))


@app.route("/products/<product_id>/delete", methods=["POST"])
@admin_required
def product_delete(product_id):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM product WHERE product_id = ?;", (product_id,))
        conn.commit()
        flash(f"已成功刪除商品 ({product_id})。", "info")
    except sqlite3.IntegrityError:
        flash(f"無法刪除商品 ({product_id})：已有歷史訂單包含此商品！", "danger")
    finally:
        conn.close()
    return redirect(url_for("products"))


# ====================================================================
# 訂單管理 (需 admin 權限，下拉選單挑選、SO格式驗證、數量正整數驗證)
# ====================================================================

@app.route("/orders")
@admin_required
def orders():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT o.order_id, o.customer_id, c.name AS customer_name, c.phone AS customer_phone,
           o.order_date, o.status, o.sales_rep,
           COALESCE(SUM(oi.quantity * oi.unit_price), 0) AS total_amount,
           COUNT(oi.product_id) AS item_count,
           GROUP_CONCAT(p.name || ' x' || oi.quantity, '、 ') AS items_summary
    FROM orders o
    JOIN customer c ON o.customer_id = c.customer_id
    LEFT JOIN order_item oi ON o.order_id = oi.order_id
    LEFT JOIN product p ON oi.product_id = p.product_id
    GROUP BY o.order_id
    ORDER BY o.order_date DESC;
    """)
    order_list = cursor.fetchall()
    conn.close()
    return render_template("orders.html", orders=order_list)


@app.route("/orders/new", methods=["GET", "POST"])
@admin_required
def order_new():
    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST":
        customer_id = request.form.get("customer_id", "").strip()
        sales_rep = request.form.get("sales_rep", "").strip()
        order_date = request.form.get("order_date", "").strip()
        order_id = request.form.get("order_id", "").strip().upper()

        if not order_date:
            order_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 自動生成 SO+數字 預設訂單編號
        if not order_id:
            today_prefix = datetime.now().strftime("SO%Y%m%d")
            cursor.execute("SELECT order_id FROM orders WHERE order_id LIKE ? ORDER BY order_id DESC LIMIT 1;", (f"{today_prefix}%",))
            last_order = cursor.fetchone()
            if last_order:
                try:
                    last_num = int(last_order["order_id"][len(today_prefix):]) + 1
                    order_id = f"{today_prefix}{last_num:03d}"
                except ValueError:
                    order_id = f"{today_prefix}001"
            else:
                order_id = f"{today_prefix}001"

        # 【需求 4：訂單編號加上 SO+數字 格式驗證 (後端第二層防護)】
        if not re.match(r"^SO\d+$", order_id):
            flash("訂單編號格式不正確！必須為「SO」開頭加上數字（例如：SO20261009001 或 SO001）。", "danger")
            conn.close()
            return redirect(url_for("order_new"))

        if not customer_id:
            flash("請由下拉選單選取訂購客戶！", "danger")
            conn.close()
            return redirect(url_for("order_new"))

        # 【需求 4 & 5：商品下拉選單與多項商品動態提交】
        product_ids = request.form.getlist("product_id")
        quantities = request.form.getlist("quantity")

        if not product_ids:
            flash("請至少選擇一項商品！", "danger")
            conn.close()
            return redirect(url_for("order_new"))

        # 檢驗商品是否重複挑選 (複合主鍵防呆)
        seen_products = set()
        items_to_insert = []

        for pid, qty_str in zip(product_ids, quantities):
            pid = pid.strip()
            qty_str = qty_str.strip()
            if not pid:
                continue

            if pid in seen_products:
                flash(f"訂單中重複選擇了相同商品 ({pid})！同一筆訂單請合併填寫數量。", "danger")
                conn.close()
                return redirect(url_for("order_new"))
            seen_products.add(pid)

            # 【需求 5：數量必須是正整數 (後端第二層防護：阻擋負數、小數、非純數字、0)】
            if not re.match(r"^[1-9]\d*$", qty_str):
                flash(f"商品 ({pid}) 的購買數量必須是正整數（大於 0 之整數，不可為 0、負數或小數）！", "danger")
                conn.close()
                return redirect(url_for("order_new"))

            qty = int(qty_str)

            # 參數化查詢商品牌價與庫存
            cursor.execute("SELECT name, unit_price, stock FROM product WHERE product_id = ?;", (pid,))
            prod = cursor.fetchone()
            if not prod:
                flash(f"找不到商品編號「{pid}」！", "danger")
                conn.close()
                return redirect(url_for("order_new"))

            if prod["stock"] < qty:
                flash(f"商品「{prod['name']}」庫存不足（現存：{prod['stock']}，欲購：{qty}）！", "danger")
                conn.close()
                return redirect(url_for("order_new"))

            items_to_insert.append({
                "product_id": pid,
                "name": prod["name"],
                "quantity": qty,
                "current_unit_price": prod["unit_price"],
            })

        if not items_to_insert:
            flash("未選取任何有效商品，請重新填寫！", "danger")
            conn.close()
            return redirect(url_for("order_new"))

        # 透過交易寫入訂單與明細 (全參數化查詢)
        try:
            cursor.execute(
                "INSERT INTO orders (order_id, customer_id, order_date, status, sales_rep) VALUES (?, ?, ?, ?, ?);",
                (order_id, customer_id, order_date, STATUS_PENDING, sales_rep or "線上業務"),
            )
            for item in items_to_insert:
                # 寫入 order_item (儲存下單當下價格，觸發第三層 CHECK 約束)
                cursor.execute(
                    "INSERT INTO order_item (order_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?);",
                    (order_id, item["product_id"], item["quantity"], item["current_unit_price"]),
                )
                # 扣除商品庫存
                cursor.execute(
                    "UPDATE product SET stock = stock - ? WHERE product_id = ?;",
                    (item["quantity"], item["product_id"]),
                )

            conn.commit()
            flash(f"訂單「{order_id}」建立成功！已保存下單當時價格並自動扣減庫存。", "success")
            conn.close()
            return redirect(url_for("order_detail", order_id=order_id))

        except sqlite3.IntegrityError as e:
            conn.rollback()
            flash(f"資料庫約束阻擋建立（請確認訂單格式或數量正整數）：{e}", "danger")
            conn.close()
            return redirect(url_for("order_new"))

    # GET 請求：查詢所有客戶與商品以供下拉選單使用
    cursor.execute("SELECT customer_id, name, phone FROM customer ORDER BY customer_id ASC;")
    customers = cursor.fetchall()

    cursor.execute("SELECT product_id, name, unit_price, stock, category FROM product ORDER BY category, product_id ASC;")
    products = cursor.fetchall()
    conn.close()

    today_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return render_template("order_new.html", customers=customers, products=products, today_str=today_str)


@app.route("/api/orders/<order_id>/status", methods=["POST"])
@admin_required
def api_order_status_update(order_id):
    """訂單列表即時更新狀態 API (全參數化)"""
    data = request.get_json(silent=True) or {}
    new_status = data.get("status") or request.form.get("status")
    if new_status not in ALLOWED_STATUSES:
        return jsonify({"success": False, "error": f"狀態僅限以下選項：{', '.join(ALLOWED_STATUSES)}"}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status = ? WHERE order_id = ?;", (new_status, order_id))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "order_id": order_id, "new_status": new_status})


@app.route("/orders/<order_id>/status", methods=["POST"])
@admin_required
def order_status_update_form(order_id):
    """標準 Form 提交更新狀態 (全參數化)"""
    new_status = request.form.get("status")
    if new_status in ALLOWED_STATUSES:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE orders SET status = ? WHERE order_id = ?;", (new_status, order_id))
        conn.commit()
        conn.close()
        flash(f"訂單「{order_id}」狀態已更新為「{new_status}」。", "success")
    else:
        flash("無效的訂單狀態選項！", "danger")
    return redirect(url_for("orders"))


@app.route("/orders/<order_id>/delete", methods=["POST"])
@admin_required
def order_delete(order_id):
    conn = get_db()
    cursor = conn.cursor()
    # 刪除前自動補回庫存 (全參數化)
    cursor.execute("SELECT product_id, quantity FROM order_item WHERE order_id = ?;", (order_id,))
    items = cursor.fetchall()
    for it in items:
        cursor.execute("UPDATE product SET stock = stock + ? WHERE product_id = ?;", (it["quantity"], it["product_id"]))
    cursor.execute("DELETE FROM orders WHERE order_id = ?;", (order_id,))
    conn.commit()
    conn.close()
    flash(f"訂單「{order_id}」已刪除，商品庫存已全數自動回補！", "info")
    return redirect(url_for("orders"))


# ====================================================================
# 專屬訂單出貨單頁面與 QR Code (/order/<訂單編號>)
# ====================================================================

@app.route("/order/<order_id>")
@admin_required
def order_detail(order_id):
    conn = get_db()
    cursor = conn.cursor()

    # 參數化查詢訂單主檔與客戶資訊
    cursor.execute("""
    SELECT o.order_id, o.order_date, o.status, o.sales_rep,
           c.customer_id, c.name AS customer_name, c.phone AS customer_phone, c.address AS customer_address
    FROM orders o
    JOIN customer c ON o.customer_id = c.customer_id
    WHERE o.order_id = ?;
    """, (order_id,))
    order = cursor.fetchone()

    if not order:
        conn.close()
        return render_template("404.html", message=f"找不到訂單編號「{order_id}」之出貨紀錄"), 404

    # 參數化查詢出貨明細 (使用下單保存之單價 unit_price)
    cursor.execute("""
    SELECT oi.order_id, oi.product_id, p.name AS product_name, p.category,
           oi.quantity, oi.unit_price, p.unit_price AS current_catalog_price,
           (oi.quantity * oi.unit_price) AS subtotal
    FROM order_item oi
    JOIN product p ON oi.product_id = p.product_id
    WHERE oi.order_id = ?
    ORDER BY oi.product_id ASC;
    """, (order_id,))
    items = cursor.fetchall()
    conn.close()

    total_amount = sum(item["subtotal"] for item in items)
    total_qty = sum(item["quantity"] for item in items)

    # 產生專屬頁面 QR Code
    target_url = request.url
    qr_base64 = generate_qr_code_base64(target_url)

    return render_template(
        "order_detail.html",
        order=order,
        items=items,
        total_amount=total_amount,
        total_qty=total_qty,
        qr_base64=qr_base64,
        target_url=target_url,
    )


# ====================================================================
# 健康檢查 API
# ====================================================================

@app.route("/api/health")
def api_health():
    return jsonify({
        "status": "online",
        "system": "訂單管理系統 (Flask + SQLite + Bootstrap 5)",
        "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })


if __name__ == "__main__":
    print("=" * 65)
    print("  訂單管理系統 (Flask + SQLite + Bootstrap 5) 正在啟動...")
    print("  安全性模式：密碼採 Werkzeug scrypt 雜湊加密，畫面零明碼")
    print("  後台權限管制：所有維護功能皆需 admin 角色")
    print("  請在瀏覽器開啟: http://127.0.0.1:5000")
    print("=" * 65)
    app.run(debug=True, host="127.0.0.1", port=5000)
