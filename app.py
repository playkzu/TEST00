"""
Flask + SQLite + Bootstrap 5 訂單管理系統
功能：
1. 四張資料表：customer, product, orders, order_item (複合主鍵)
2. 管理員登入後可維護客戶、商品、訂單
3. 新增訂單：客戶下拉選單、商品一次勾選多項並填寫數量、即時計算金額
4. order_item 保存下單當時單價，商品後續改價不影響歷史訂單
5. 訂單狀態：處理中 / 已出貨 / 已完成 / 已取消，可在列表直接即時更新
6. 專屬訂單與出貨單頁面 /order/<訂單編號>，包含 QR Code 與列印優化
7. 內建 5 筆繁體中文測試資料與管理員帳號
"""

import base64
import functools
import io
import os
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
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "order-system-super-secret-key-2026")
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "orders.db")


def get_db():
    """取得資料庫連線並開啟 Row 字典映射與外鍵約束"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    """初始化資料庫結構與預設測試資料"""
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

    # 2. 商品資料表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS product (
        product_id  TEXT PRIMARY KEY,
        name        TEXT NOT NULL,
        unit_price  REAL NOT NULL CHECK (unit_price >= 0),
        stock       INTEGER NOT NULL CHECK (stock >= 0),
        category    TEXT
    );
    """)

    # 3. 訂單資料表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        order_id     TEXT PRIMARY KEY,
        customer_id  TEXT NOT NULL,
        order_date   TEXT NOT NULL,
        status       TEXT NOT NULL CHECK (status IN ('處理中', '已出貨', '已完成', '已取消')),
        sales_rep    TEXT,
        FOREIGN KEY (customer_id) REFERENCES customer(customer_id)
            ON UPDATE CASCADE ON DELETE RESTRICT
    );
    """)

    # 4. 訂單明細資料表 (以訂單編號 + 商品編號為複合主鍵)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_item (
        order_id    TEXT NOT NULL,
        product_id  TEXT NOT NULL,
        quantity    INTEGER NOT NULL CHECK (quantity > 0),
        unit_price  REAL NOT NULL CHECK (unit_price >= 0),
        PRIMARY KEY (order_id, product_id),
        FOREIGN KEY (order_id) REFERENCES orders(order_id)
            ON UPDATE CASCADE ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES product(product_id)
            ON UPDATE CASCADE ON DELETE RESTRICT
    );
    """)

    # 5. 管理員帳號資料表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admin_user (
        username      TEXT PRIMARY KEY,
        password_hash TEXT NOT NULL,
        display_name  TEXT NOT NULL
    );
    """)

    # 檢查是否已有管理員
    cursor.execute("SELECT COUNT(*) FROM admin_user;")
    if cursor.fetchone()[0] == 0:
        default_pwd_hash = generate_password_hash("admin123")
        cursor.execute(
            "INSERT INTO admin_user (username, password_hash, display_name) VALUES (?, ?, ?);",
            ("admin", default_pwd_hash, "系統管理員"),
        )

    # 檢查並插入 5 筆繁體中文測試資料 (如果 customer 為空)
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
            "INSERT INTO customer (customer_id, name, phone, address, created_date) VALUES (?, ?, ?, ?, ?)",
            customers,
        )

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
            "INSERT INTO product (product_id, name, unit_price, stock, category) VALUES (?, ?, ?, ?, ?)",
            products,
        )

    cursor.execute("SELECT COUNT(*) FROM orders;")
    if cursor.fetchone()[0] == 0:
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

    cursor.execute("SELECT COUNT(*) FROM order_item;")
    if cursor.fetchone()[0] == 0:
        order_items = [
            ("ORD20260301", "P001", 1, 3200.0),
            ("ORD20260301", "P002", 1, 2800.0),
            ("ORD20260302", "P003", 1, 4500.0),
            ("ORD20260302", "P005", 2, 650.0),
            ("ORD20260303", "P004", 2, 1280.0),
            ("ORD20260304", "P001", 1, 3000.0),  # 保存歷史下單特價 3000
            ("ORD20260304", "P005", 3, 650.0),
            ("ORD20260305", "P002", 2, 2800.0),
        ]
        cursor.executemany(
            "INSERT INTO order_item (order_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
            order_items,
        )

    conn.commit()
    conn.close()


# 初始化資料庫
init_db()


def login_required(view):
    """驗證管理員登入裝飾器"""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if not session.get("logged_in"):
            flash("請先登入管理員帳號以繼續操作。", "warning")
            return redirect(url_for("login", next=request.path))
        return view(**kwargs)
    return wrapped_view


def generate_qr_code_base64(data_text):
    """將文字轉換為 QR Code Base64 PNG 圖片"""
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
# 身份驗證路由 (登入、登出)
# ====================================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM admin_user WHERE username = ?;", (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["logged_in"] = True
            session["username"] = user["username"]
            session["display_name"] = user["display_name"]
            flash(f"歡迎回來，{user['display_name']}！", "success")
            next_url = request.args.get("next")
            return redirect(next_url or url_for("dashboard"))
        else:
            flash("帳號或密碼錯誤，請重新輸入。（預設帳密：admin / admin123）", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("您已成功登出系統。", "info")
    return redirect(url_for("login"))


# ====================================================================
# 儀表板
# ====================================================================

@app.route("/")
def index():
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()
    cursor = conn.cursor()

    # 統計數據
    cursor.execute("SELECT COUNT(*) FROM customer;")
    customer_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM product;")
    product_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM orders;")
    order_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM orders WHERE status = '處理中';")
    pending_count = cursor.fetchone()[0]

    cursor.execute("""
    SELECT COALESCE(SUM(quantity * unit_price), 0)
    FROM order_item oi
    JOIN orders o ON oi.order_id = o.order_id
    WHERE o.status != '已取消';
    """)
    total_sales = cursor.fetchone()[0]

    # 最近 5 筆訂單
    cursor.execute("""
    SELECT o.order_id, c.name AS customer_name, o.order_date, o.status, o.sales_rep,
           COALESCE(SUM(oi.quantity * oi.unit_price), 0) AS total_amount,
           COUNT(oi.product_id) AS item_count
    FROM orders o
    JOIN customer c ON o.customer_id = c.customer_id
    LEFT JOIN order_item oi ON o.order_id = oi.order_id
    GROUP BY o.order_id
    ORDER BY o.order_date DESC
    LIMIT 5;
    """)
    recent_orders = cursor.fetchall()

    # 低庫存預警商品 (庫存 < 30)
    cursor.execute("SELECT product_id, name, unit_price, stock, category FROM product WHERE stock < 30 ORDER BY stock ASC;")
    low_stock_products = cursor.fetchall()

    conn.close()
    return render_template(
        "dashboard.html",
        customer_count=customer_count,
        product_count=product_count,
        order_count=order_count,
        pending_count=pending_count,
        total_sales=total_sales,
        recent_orders=recent_orders,
        low_stock_products=low_stock_products,
    )


# ====================================================================
# 客戶管理 (Customer CRUD)
# ====================================================================

@app.route("/customers")
@login_required
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
@login_required
def customer_create():
    customer_id = request.form.get("customer_id", "").strip().upper()
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    address = request.form.get("address", "").strip()

    if not customer_id or not name:
        flash("客戶編號與客戶名稱為必填欄位！", "danger")
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
        flash(f"已成功建立客戶「{name}」({customer_id})！", "success")
    except sqlite3.IntegrityError:
        flash(f"客戶編號「{customer_id}」已存在，請使用其他編號。", "danger")
    finally:
        conn.close()

    return redirect(url_for("customers"))


@app.route("/customers/<customer_id>/edit", methods=["POST"])
@login_required
def customer_update(customer_id):
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    address = request.form.get("address", "").strip()

    if not name:
        flash("客戶名稱為必填！", "danger")
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
@login_required
def customer_delete(customer_id):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM customer WHERE customer_id = ?;", (customer_id,))
        conn.commit()
        flash(f"已成功刪除客戶 ({customer_id})。", "info")
    except sqlite3.IntegrityError:
        flash(f"無法刪除客戶 ({customer_id})，因為該客戶已有相關訂單紀錄！", "danger")
    finally:
        conn.close()
    return redirect(url_for("customers"))


# ====================================================================
# 商品管理 (Product CRUD)
# ====================================================================

@app.route("/products")
@login_required
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
@login_required
def product_create():
    product_id = request.form.get("product_id", "").strip().upper()
    name = request.form.get("name", "").strip()
    category = request.form.get("category", "").strip()
    try:
        unit_price = float(request.form.get("unit_price", 0))
        stock = int(request.form.get("stock", 0))
    except ValueError:
        flash("單價或庫存格式不正確！", "danger")
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
        flash(f"商品編號「{product_id}」已存在或違反約束條件！", "danger")
    finally:
        conn.close()

    return redirect(url_for("products"))


@app.route("/products/<product_id>/edit", methods=["POST"])
@login_required
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
        flash(f"商品「{name}」資訊已成功更新！（現行牌價變更為 NT$ {unit_price:,.0f}，歷史訂單仍保存下單當下價格不受影響）", "success")
    except sqlite3.IntegrityError as e:
        flash(f"更新失敗：{e}", "danger")
    finally:
        conn.close()

    return redirect(url_for("products"))


@app.route("/products/<product_id>/delete", methods=["POST"])
@login_required
def product_delete(product_id):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM product WHERE product_id = ?;", (product_id,))
        conn.commit()
        flash(f"商品 ({product_id}) 已刪除。", "info")
    except sqlite3.IntegrityError:
        flash(f"無法刪除商品 ({product_id})，因為已有歷史訂單包含此商品！", "danger")
    finally:
        conn.close()
    return redirect(url_for("products"))


# ====================================================================
# 訂單管理 (Orders CRUD、下拉勾選多項、在線更新狀態)
# ====================================================================

@app.route("/orders")
@login_required
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
@login_required
def order_new():
    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST":
        customer_id = request.form.get("customer_id", "").strip()
        sales_rep = request.form.get("sales_rep", "").strip()
        order_date = request.form.get("order_date", "").strip()
        order_id = request.form.get("order_id", "").strip()

        if not order_date:
            order_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 自動生成訂單編號
        if not order_id:
            today_prefix = datetime.now().strftime("ORD%Y%m%d")
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

        # 取得被勾選的商品列表
        selected_product_ids = request.form.getlist("selected_products")

        if not customer_id:
            flash("請選擇客戶！", "danger")
            conn.close()
            return redirect(url_for("order_new"))

        if not selected_product_ids:
            flash("請至少勾選一項要購買的商品！", "danger")
            conn.close()
            return redirect(url_for("order_new"))

        items_to_insert = []
        for pid in selected_product_ids:
            qty_str = request.form.get(f"quantity_{pid}", "1").strip()
            try:
                qty = int(qty_str)
                if qty <= 0:
                    raise ValueError
            except ValueError:
                flash(f"商品 {pid} 的購買數量必須大於 0！", "danger")
                conn.close()
                return redirect(url_for("order_new"))

            # 查詢商品當前定價與庫存
            cursor.execute("SELECT name, unit_price, stock FROM product WHERE product_id = ?;", (pid,))
            prod = cursor.fetchone()
            if not prod:
                flash(f"找不到商品 {pid}！", "danger")
                conn.close()
                return redirect(url_for("order_new"))

            if prod["stock"] < qty:
                flash(f"商品「{prod['name']}」庫存不足（目前庫存：{prod['stock']}，欲購買：{qty}）！", "danger")
                conn.close()
                return redirect(url_for("order_new"))

            # 記錄下單當時單價 (unit_price) 與扣減庫存量
            items_to_insert.append({
                "product_id": pid,
                "name": prod["name"],
                "quantity": qty,
                "current_unit_price": prod["unit_price"],
            })

        # 透過交易同時寫入 orders、order_item 並扣減庫存
        try:
            cursor.execute(
                "INSERT INTO orders (order_id, customer_id, order_date, status, sales_rep) VALUES (?, ?, ?, ?, ?);",
                (order_id, customer_id, order_date, "處理中", sales_rep or "線上業務"),
            )
            for item in items_to_insert:
                # 寫入明細，保存下單當時價格
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
            flash(f"訂單「{order_id}」建立成功！已扣除庫存並保存當前下單價格。", "success")
            conn.close()
            return redirect(url_for("order_detail", order_id=order_id))

        except sqlite3.IntegrityError as e:
            conn.rollback()
            flash(f"建立訂單失敗：{e}", "danger")
            conn.close()
            return redirect(url_for("order_new"))

    # GET 頁面：載入所有客戶與商品
    cursor.execute("SELECT customer_id, name, phone FROM customer ORDER BY customer_id ASC;")
    customers = cursor.fetchall()

    cursor.execute("SELECT product_id, name, unit_price, stock, category FROM product ORDER BY category, product_id ASC;")
    products = cursor.fetchall()
    conn.close()

    today_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    return render_template("order_new.html", customers=customers, products=products, today_str=today_str)


@app.route("/api/orders/<order_id>/status", methods=["POST"])
@login_required
def api_order_status_update(order_id):
    """供列表即時下拉選單切換訂單狀態 (AJAX)"""
    data = request.get_json(silent=True) or {}
    new_status = data.get("status") or request.form.get("status")
    allowed = ["處理中", "已出貨", "已完成", "已取消"]
    if new_status not in allowed:
        return jsonify({"success": False, "error": f"狀態必須為以下之一：{', '.join(allowed)}"}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status = ? WHERE order_id = ?;", (new_status, order_id))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "order_id": order_id, "new_status": new_status})


@app.route("/orders/<order_id>/status", methods=["POST"])
@login_required
def order_status_update_form(order_id):
    """支援標準 HTML Form 提交更新狀態"""
    new_status = request.form.get("status")
    allowed = ["處理中", "已出貨", "已完成", "已取消"]
    if new_status in allowed:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE orders SET status = ? WHERE order_id = ?;", (new_status, order_id))
        conn.commit()
        conn.close()
        flash(f"訂單「{order_id}」狀態已更新為「{new_status}」。", "success")
    else:
        flash("無效的訂單狀態！", "danger")
    return redirect(url_for("orders"))


@app.route("/orders/<order_id>/delete", methods=["POST"])
@login_required
def order_delete(order_id):
    conn = get_db()
    cursor = conn.cursor()
    # 刪除訂單時先加回庫存
    cursor.execute("SELECT product_id, quantity FROM order_item WHERE order_id = ?;", (order_id,))
    items = cursor.fetchall()
    for it in items:
        cursor.execute("UPDATE product SET stock = stock + ? WHERE product_id = ?;", (it["quantity"], it["product_id"]))
    cursor.execute("DELETE FROM orders WHERE order_id = ?;", (order_id,))
    conn.commit()
    conn.close()
    flash(f"訂單「{order_id}」已成功刪除，相關庫存已自動回補！", "info")
    return redirect(url_for("orders"))


# ====================================================================
# 專屬訂單頁面與出貨單 QR Code (/order/<訂單編號>)
# ====================================================================

@app.route("/order/<order_id>")
def order_detail(order_id):
    conn = get_db()
    cursor = conn.cursor()

    # 查詢訂單主檔與客戶資料
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
        return render_template("404.html", message=f"找不到訂單編號「{order_id}」的資料"), 404

    # 查詢訂單明細 (使用下單時保存的 unit_price，並同時查出商品目前牌價以供對比)
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
# 健康檢查與 API
# ====================================================================

@app.route("/api/health")
def api_health():
    return jsonify({
        "status": "online",
        "system": "訂單管理系統 (Flask + SQLite + Bootstrap 5)",
        "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })


if __name__ == "__main__":
    print("=" * 60)
    print("  訂單管理系統 (Flask + SQLite + Bootstrap 5) 正在啟動...")
    print("  預設管理員帳號: admin")
    print("  預設管理員密碼: admin123")
    print("  請在瀏覽器開啟: http://127.0.0.1:5000")
    print("=" * 60)
    app.run(debug=True, host="127.0.0.1", port=5000)
