import os
import time
import uuid
import pytest
from app import app, init_db, get_db

@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    init_db()  # 確保資料庫結構與預設 5 筆測試資料存在
    with app.test_client() as client:
        yield client

def login_as_admin(client):
    """輔助函式：登入管理員帳號"""
    return client.post("/login", data={
        "username": "admin",
        "password": "admin123"
    }, follow_redirects=True)

def test_login_page(client):
    """測試登入頁面正常顯示"""
    response = client.get("/login")
    assert response.status_code == 200
    assert "管理員登入" in response.get_data(as_text=True)

def test_login_success_and_logout(client):
    """測試管理員帳號密碼登入與登出"""
    # 成功登入
    res_login = login_as_admin(client)
    assert res_login.status_code == 200
    assert "營運儀表板" in res_login.get_data(as_text=True)

    # 登出
    res_logout = client.get("/logout", follow_redirects=True)
    assert res_logout.status_code == 200
    assert "管理員登入" in res_logout.get_data(as_text=True)

def test_login_failure(client):
    """測試錯誤密碼登入被拒絕"""
    res = client.post("/login", data={
        "username": "admin",
        "password": "wrongpassword"
    }, follow_redirects=True)
    assert "帳號或密碼錯誤" in res.get_data(as_text=True)

def test_protected_routes_require_login(client):
    """測試未登入時存取管理端點自動導向登入頁"""
    for route in ["/dashboard", "/orders", "/orders/new", "/customers", "/products"]:
        res = client.get(route)
        assert res.status_code == 302
        assert "/login" in res.headers["Location"]

def test_initial_test_data_loaded(client):
    """驗證各表至少各有 5 筆繁體中文測試資料"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM customer;")
    assert cursor.fetchone()[0] >= 5

    cursor.execute("SELECT COUNT(*) FROM product;")
    assert cursor.fetchone()[0] >= 5

    cursor.execute("SELECT COUNT(*) FROM orders;")
    assert cursor.fetchone()[0] >= 5

    cursor.execute("SELECT COUNT(*) FROM order_item;")
    assert cursor.fetchone()[0] >= 5

    conn.close()

def test_create_order_with_multiple_products(client):
    """測試新增訂單：客戶下拉、一次勾選多項商品與數量、保存當時單價與扣減庫存"""
    login_as_admin(client)

    test_ord_id = f"TEST_ORD_{uuid.uuid4().hex[:6].upper()}"

    # 取得 P001 與 P002 當前庫存與單價
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT stock, unit_price FROM product WHERE product_id = 'P001';")
    p1_stock, p1_price = cur.fetchone()
    cur.execute("SELECT stock, unit_price FROM product WHERE product_id = 'P002';")
    p2_stock, p2_price = cur.fetchone()
    conn.close()

    order_payload = {
        "order_id": test_ord_id,
        "customer_id": "C001",
        "sales_rep": "測試業務員",
        "order_date": "2026-10-09 10:00:00",
        "selected_products": ["P001", "P002"],
        "quantity_P001": "2",
        "quantity_P002": "1",
    }

    res = client.post("/orders/new", data=order_payload, follow_redirects=True)
    assert res.status_code == 200
    assert "銷貨出貨單" in res.get_data(as_text=True)

    # 驗證資料庫資料與庫存扣減
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT customer_id, status FROM orders WHERE order_id = ?;", (test_ord_id,))
    ord_row = cur.fetchone()
    assert ord_row["customer_id"] == "C001"
    assert ord_row["status"] == "處理中"

    # 驗證明細保存下單當時單價
    cur.execute("SELECT product_id, quantity, unit_price FROM order_item WHERE order_id = ? ORDER BY product_id;", (test_ord_id,))
    items = cur.fetchall()
    assert len(items) == 2
    assert items[0]["product_id"] == "P001"
    assert items[0]["quantity"] == 2
    assert items[0]["unit_price"] == p1_price
    assert items[1]["product_id"] == "P002"
    assert items[1]["quantity"] == 1
    assert items[1]["unit_price"] == p2_price

    # 驗證庫存已被扣除
    cur.execute("SELECT stock FROM product WHERE product_id = 'P001';")
    assert cur.fetchone()[0] == p1_stock - 2
    cur.execute("SELECT stock FROM product WHERE product_id = 'P002';")
    assert cur.fetchone()[0] == p2_stock - 1

    conn.close()

def test_order_status_update_inplace(client):
    """測試在列表直接即時更新訂單狀態 (處理中 -> 已出貨 -> 已完成 -> 已取消)"""
    login_as_admin(client)

    # 透過 AJAX API 更新狀態
    res = client.post("/api/orders/ORD20260301/status", json={"status": "已出貨"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["new_status"] == "已出貨"

    # 驗證資料庫
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT status FROM orders WHERE order_id = 'ORD20260301';")
    assert cur.fetchone()[0] == "已出貨"
    conn.close()

def test_order_detail_and_qr_code(client):
    """測試每張訂單專屬頁面 /order/<訂單編號> 與 QR Code 產生"""
    res = client.get("/order/ORD20260301")
    assert res.status_code == 200
    text = res.get_data(as_text=True)
    assert "銷貨出貨單" in text
    assert "ORD20260301" in text
    assert "data:image/png;base64," in text  # 驗證 QR Code Base64 圖片產生

def test_historical_price_preservation(client):
    """核心測試：商品改價後，歷史訂單中的下單單價不受任何影響"""
    login_as_admin(client)

    test_ord_id = f"PRICE_TEST_{uuid.uuid4().hex[:6].upper()}"

    # 先查詢當前 P005 價格作為基準
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT unit_price FROM product WHERE product_id = 'P005';")
    original_price = cur.fetchone()[0]
    conn.close()

    new_price = original_price + 800.0

    # 建立一筆測試訂單，下單 P005
    client.post("/orders/new", data={
        "order_id": test_ord_id,
        "customer_id": "C002",
        "selected_products": ["P005"],
        "quantity_P005": "1",
    })

    # 管理員將商品 P005 單價大幅上調
    client.post("/products/P005/edit", data={
        "name": "不鏽鋼雙層真空保溫杯",
        "unit_price": str(new_price),
        "stock": "100",
        "category": "生活居家"
    })

    # 驗證 P005 目前牌價變為 new_price
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT unit_price FROM product WHERE product_id = 'P005';")
    assert cur.fetchone()[0] == new_price

    # 驗證歷史訂單中的單價依然維持下單時的 original_price！
    cur.execute("SELECT unit_price FROM order_item WHERE order_id = ? AND product_id = 'P005';", (test_ord_id,))
    assert cur.fetchone()[0] == original_price
    conn.close()
