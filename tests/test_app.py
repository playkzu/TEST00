import os
import sys
import re
import sqlite3
import uuid

# 確保專案根目錄在 sys.path 中，避免直接執行 pytest 時發生 ModuleNotFoundError: No module named 'app'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from app import app, init_db, get_db
from werkzeug.security import check_password_hash

@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    init_db()  # 確保資料庫結構與預設測試資料就緒
    with app.test_client() as client:
        yield client

def login_as_admin(client):
    """輔助函式：登入管理員帳號"""
    return client.post("/login", data={
        "username": "admin",
        "password": "admin123"
    }, follow_redirects=True)

# ====================================================================
# 需求 1：管理員密碼改以 Werkzeug 雜湊儲存，程式與畫面不得出現明碼
# ====================================================================

def test_admin_password_is_hashed_and_no_plaintext(client):
    """驗證資料庫中的管理員密碼以安全雜湊格式儲存，且畫面中不含明碼密碼"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT password_hash FROM admin_user WHERE username = ?;", ("admin",))
    user = cur.fetchone()
    conn.close()

    assert user is not None
    pwd_hash = user["password_hash"]
    # 確保是 Werkzeug 支援的安全雜湊 (如 scrypt 或 pbkdf2)，非明碼
    assert pwd_hash.startswith("scrypt:") or pwd_hash.startswith("pbkdf2:")
    assert "admin123" not in pwd_hash
    # 驗證 check_password_hash 能正確比對
    assert check_password_hash(pwd_hash, "admin123") is True

    # 檢查登入畫面 HTML 中無明碼密碼
    res = client.get("/login")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "admin123" not in html
    assert 'value="admin123"' not in html

# ====================================================================
# 需求 2：後台所有頁面需登入 (Session) 且角色為管理員才能進入
# ====================================================================

def test_backend_pages_require_admin_login(client):
    """驗證未登入訪客存取任何後台頁面均被強制重導向至登入頁"""
    backend_urls = [
        "/dashboard",
        "/customers",
        "/products",
        "/orders",
        "/orders/new",
        "/order/SO20260301",
    ]
    for url in backend_urls:
        res = client.get(url)
        assert res.status_code == 302
        assert "/login" in res.headers["Location"]

def test_non_admin_role_cannot_access_backend(client):
    """驗證 Session 中角色非 admin 時，存取後台會被攔截阻擋"""
    with client.session_transaction() as sess:
        sess["logged_in"] = True
        sess["username"] = "guest_user"
        sess["role"] = "guest"  # 非管理員角色

    res = client.get("/dashboard", follow_redirects=False)
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]

# ====================================================================
# 需求 3：所有 SQL 改為參數化查詢 (? 佔位符)
# ====================================================================

def test_sql_injection_defense_via_parameterized_query(client):
    """驗證即使輸入 SQL 注入惡意語法，因使用參數化查詢亦能被安全處理"""
    # 嘗試使用 SQL Injection 帳號登入
    res = client.post("/login", data={
        "username": "' OR '1'='1' --",
        "password": "wrong"
    }, follow_redirects=True)
    assert "帳號或密碼錯誤" in res.get_data(as_text=True)

# ====================================================================
# 需求 4：客戶與商品改為下拉選單，訂單編號加上 SO+數字 格式驗證
# ====================================================================

def test_order_new_page_has_dropdowns(client):
    """驗證新增訂單頁面具備客戶下拉選單與商品下拉選單"""
    login_as_admin(client)
    res = client.get("/orders/new")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    # 客戶下拉選單
    assert 'select class="form-select" id="customer_id" name="customer_id"' in html
    # 商品下拉選單
    assert 'product-dropdown' in html
    assert 'name="product_id"' in html

def test_order_id_valid_format_so_plus_digits(client):
    """驗證訂單編號符合 SO+數字 格式時可成功建立"""
    login_as_admin(client)
    valid_order_id = f"SO{uuid.uuid4().int % 100000000}"

    payload = {
        "order_id": valid_order_id,
        "customer_id": "C001",
        "sales_rep": "李業務",
        "order_date": "2026-10-09 12:00:00",
        "product_id": ["P001", "P002"],
        "quantity": ["1", "2"]
    }
    res = client.post("/orders/new", data=payload, follow_redirects=True)
    assert res.status_code == 200
    assert valid_order_id in res.get_data(as_text=True)

    # 確認資料庫確實寫入
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT order_id FROM orders WHERE order_id = ?;", (valid_order_id,))
    assert cur.fetchone() is not None
    conn.close()

def test_order_id_invalid_format_blocked(client):
    """驗證訂單編號不符合 SO+數字 格式時會被後端與資料庫嚴格阻擋"""
    login_as_admin(client)

    invalid_ids = ["ORD20260301", "SOabc", "12345", "SO", "MY_ORDER_1"]
    for bad_id in invalid_ids:
        payload = {
            "order_id": bad_id,
            "customer_id": "C001",
            "sales_rep": "李業務",
            "order_date": "2026-10-09 12:00:00",
            "product_id": ["P001"],
            "quantity": ["1"]
        }
        res = client.post("/orders/new", data=payload, follow_redirects=True)
        # 後端應阻擋並跳出格式錯誤提示
        assert "訂單編號格式不正確" in res.get_data(as_text=True)

        # 確認資料庫內不存在該違規編號
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT order_id FROM orders WHERE order_id = ?;", (bad_id,))
        assert cur.fetchone() is None
        conn.close()

# ====================================================================
# 需求 5：數量必須是正整數，前端、後端、資料庫 CHECK 三層都要擋
# ====================================================================

def test_quantity_non_positive_integer_blocked_by_backend(client):
    """驗證後端阻擋數量為 0、負數、小數等非正整數"""
    login_as_admin(client)
    test_id = f"SO{uuid.uuid4().int % 100000000}"

    invalid_quantities = ["0", "-1", "-5", "1.5", "2.8", "abc", ""]
    for bad_qty in invalid_quantities:
        payload = {
            "order_id": test_id,
            "customer_id": "C001",
            "product_id": ["P001"],
            "quantity": [bad_qty]
        }
        res = client.post("/orders/new", data=payload, follow_redirects=True)
        assert "數量必須是正整數" in res.get_data(as_text=True)

def test_quantity_check_constraint_in_database():
    """驗證資料庫 CHECK 約束層嚴格阻擋 0、負數、小數與非整數型別"""
    conn = get_db()
    cur = conn.cursor()

    # 嘗試在資料庫直接 INSERT 數量為 0
    with pytest.raises(sqlite3.IntegrityError):
        cur.execute("INSERT INTO order_item VALUES (?, ?, ?, ?);", ("SO20260301", "P004", 0, 100))

    # 嘗試在資料庫直接 INSERT 數量為負數 -2
    with pytest.raises(sqlite3.IntegrityError):
        cur.execute("INSERT INTO order_item VALUES (?, ?, ?, ?);", ("SO20260301", "P004", -2, 100))

    # 嘗試在資料庫直接 INSERT 數量為浮點數 1.5
    with pytest.raises(sqlite3.IntegrityError):
        cur.execute("INSERT INTO order_item VALUES (?, ?, ?, ?);", ("SO20260301", "P004", 1.5, 100))

    conn.close()

# ====================================================================
# 價格快照機制檢驗
# ====================================================================

def test_historical_price_preservation(client):
    """驗證歷史訂單保存下單當時單價，商品改價不影響歷史訂單"""
    login_as_admin(client)

    test_ord_id = f"SO{uuid.uuid4().int % 100000000}"

    # 查詢當前 P005 價格
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT unit_price FROM product WHERE product_id = 'P005';")
    original_price = cur.fetchone()[0]
    conn.close()

    new_price = original_price + 600.0

    # 建立訂單，下單 P005
    client.post("/orders/new", data={
        "order_id": test_ord_id,
        "customer_id": "C002",
        "product_id": ["P005"],
        "quantity": ["1"],
    })

    # 管理員將商品 P005 改價
    client.post("/products/P005/edit", data={
        "name": "不鏽鋼雙層真空保溫杯",
        "unit_price": str(new_price),
        "stock": "100",
        "category": "生活居家"
    })

    # 驗證牌價已更新，但歷史訂單單價凍結為 original_price
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT unit_price FROM product WHERE product_id = 'P005';")
    assert cur.fetchone()[0] == new_price
    cur.execute("SELECT unit_price FROM order_item WHERE order_id = ? AND product_id = 'P005';", (test_ord_id,))
    assert cur.fetchone()[0] == original_price
    conn.close()
