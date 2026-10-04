import os
import re
import random
import urllib.parse
import urllib.request
from datetime import datetime
from flask import Flask, render_template, jsonify, request, send_from_directory

app = Flask(__name__)

# 內存存儲預約紀錄（可擴展為資料庫持久化）
APPOINTMENTS = []

# 堡量建設建案官方資料庫
PROJECTS = [
    {
        "id": "wuju",
        "name": "堡量豐華梧居墅",
        "subtitle": "THE WUJU VILLA",
        "category": "villa",
        "category_name": "電梯別墅名邸",
        "status": "全新公開・熱烈預約中",
        "badge_class": "badge-hot",
        "location": "彰化縣溪湖鎮西學路2號（接待會館）",
        "phone": "04-8851979",
        "specs": "溪湖生活核心 | 頂級精工傳世電梯別墅",
        "architect": "堡量建設建築美學團隊",
        "image": "/dist/img/exterior.png",
        "tag": "溪湖西學路正核心",
        "vr_url": "https://livetour.istaging.com/6e0ca763-4197-48f5-839f-029452cb8516",
        "video_url": "/dist/img/video.mp4",
        "fb_url": "https://www.facebook.com/profile.php?id=61575503607806&locale=zh_TW",
        "map_url": "https://maps.app.goo.gl/qXQ2PqcAejrucA1i6",
        "description": "堡量建設於彰化溪湖西學路核心特區，精鑄頂級電梯別墅名邸「堡量豐華梧居墅」。結合現代俐落外觀、綠意人文生活圈與航太級制震精工工法，為榮耀家族打造傳承世代的莊園名邸。"
    }
]

# Google Form 官方線上同步填單端點
GOOGLE_FORM_URL = "https://docs.google.com/forms/u/1/d/e/1FAIpQLSeT8Kb8YZn2D4GEzSl1zJfoEOHtkwMeFAaOLSJllm7XAQ3xvA/formResponse"
GOOGLE_FORM_ENTRY_MAP = {
    "name": "entry.949233864",
    "tel": "entry.603148494",
    "line": "entry.1520546596",
    "content": "entry.296508673"
}

@app.route("/")
def index():
    """首頁：渲染堡量建設「堡量豐華梧居墅」官方首頁"""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return render_template(
        "index.html",
        current_time=current_time,
        projects=PROJECTS,
        total_projects=len(PROJECTS),
        company_name="堡量建設",
        project_name="堡量豐華梧居墅",
        phone="04-8851979",
        address="彰化縣溪湖鎮西學路2號"
    )

@app.route("/dist/<path:filename>")
def serve_dist(filename):
    """提供 dist 靜態資源（CSS、JS、圖片、影片等）"""
    dist_dir = os.path.join(app.static_folder, "dist")
    return send_from_directory(dist_dir, filename)

@app.route("/cover.png")
def serve_cover():
    """提供社群分享封面縮圖 cover.png"""
    return send_from_directory(app.static_folder, "cover.png")

@app.route("/api/projects", methods=["GET"])
def api_projects():
    """提供建案列表與分類過濾 API"""
    category = request.args.get("category", "all")
    if category == "all":
        filtered = PROJECTS
    else:
        filtered = [p for p in PROJECTS if p.get("category") == category]
    return jsonify({
        "status": "success",
        "company": "堡量建設",
        "count": len(filtered),
        "data": filtered
    })

@app.route("/api/appointment", methods=["POST"])
def api_appointment():
    """線上 VIP 預約賞屋表單提交 API，同步記錄至內存並轉發 Google 表單"""
    data = request.get_json(silent=True) or request.form.to_dict()
    
    if not data:
        return jsonify({
            "status": "error",
            "message": "請提供預約資料"
        }), 400

    name = data.get("name", "").strip()
    gender = data.get("gender", "貴賓").strip()
    # 支援 phone 或 tel 欄位命名
    phone = data.get("phone", data.get("tel", "")).strip()
    line_id = data.get("line", data.get("line_id", "")).strip()
    email = data.get("email", "").strip()
    project = data.get("project", "堡量豐華梧居墅").strip()
    visit_date = data.get("date", datetime.now().strftime("%Y-%m-%d")).strip()
    time_slot = data.get("time_slot", "全天皆可").strip()
    budget = data.get("budget", "").strip()
    notes = data.get("notes", data.get("content", "")).strip()

    # 驗證必填欄位
    errors = []
    if not name or len(name) < 2:
        errors.append("請填寫貴賓姓名（至少 2 個字元）")
    
    clean_phone = re.sub(r"[\s\-]", "", phone)
    if not phone or (not re.match(r"^09\d{8}$", clean_phone) and not re.match(r"^0\d{8,9}$", clean_phone)):
        errors.append("請填寫正確的手機號碼（格式如：0912-345-678）")

    if errors:
        return jsonify({
            "status": "error",
            "message": "；".join(errors),
            "errors": errors
        }), 400

    # 產生專屬 VIP 預約編號
    timestamp_str = datetime.now().strftime("%Y%m%d")
    random_code = f"{random.randint(1000, 9999)}"
    reservation_id = f"VIP-BL-{timestamp_str}-{random_code}"

    record = {
        "reservation_id": reservation_id,
        "name": name,
        "gender": gender,
        "phone": phone,
        "line": line_id,
        "email": email,
        "project": project,
        "date": visit_date,
        "time_slot": time_slot,
        "budget": budget,
        "notes": notes,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    APPOINTMENTS.append(record)

    # 嘗試同步轉發至 Google 表單以保證業務端即時接收
    try:
        gf_payload = urllib.parse.urlencode({
            GOOGLE_FORM_ENTRY_MAP["name"]: name,
            GOOGLE_FORM_ENTRY_MAP["tel"]: phone,
            GOOGLE_FORM_ENTRY_MAP["line"]: line_id,
            GOOGLE_FORM_ENTRY_MAP["content"]: notes
        }).encode("utf-8")
        req_gf = urllib.request.Request(
            GOOGLE_FORM_URL,
            data=gf_payload,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        urllib.request.urlopen(req_gf, timeout=2.5)
    except Exception as e:
        app.logger.info(f"Google Form background sync status: {e}")

    return jsonify({
        "status": "success",
        "message": f"尊榮貴賓 {name} 您好！您的鑑賞預約已成功受理，專人將儘速與您聯繫。",
        "reservation_id": reservation_id,
        "details": {
            "project": project,
            "date": visit_date,
            "time_slot": time_slot,
            "phone_masked": phone[:4] + "***" + phone[-3:] if len(phone) >= 7 else phone
        }
    }), 201

@app.route("/api/greet", methods=["GET"])
def api_greet():
    """提供前端測試與健康度檢查 API"""
    return jsonify({
        "status": "success",
        "company": "堡量建設",
        "project": "堡量豐華梧居墅",
        "phone": "04-8851979",
        "address": "彰化縣溪湖鎮西學路2號",
        "message": "來自 Flask 後端的問候：歡迎光臨 堡量建設「堡量豐華梧居墅」官方網站！",
        "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

if __name__ == "__main__":
    print("堡量建設「堡量豐華梧居墅」官方網站伺服器正在啟動...")
    print("請在瀏覽器開啟: http://127.0.0.1:5000")
    app.run(debug=True, host="127.0.0.1", port=5000)
