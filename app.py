from flask import Flask, render_template, jsonify, request
from datetime import datetime
import re
import random

app = Flask(__name__)

# 內存存儲預約紀錄（可擴展為資料庫持久化）
APPOINTMENTS = []

# 建案資料庫
PROJECTS = [
    {
        "id": "pinnacle",
        "name": "保量・御峰",
        "subtitle": "THE PINNACLE RESIDENCE",
        "category": "residence",
        "category_name": "豪宅名邸",
        "status": "熱銷倒數 95%",
        "badge_class": "badge-hot",
        "location": "台北市信義計畫區・松勇路首排",
        "specs": "115 ~ 180 坪 | 一層一戶極景梯廳",
        "architect": "普立茲克大師團隊聯手巨作",
        "image": "/static/images/hero-building.jpg",
        "tag": "頂級制震地標",
        "description": "聳立於信義核心地段，獨攬台北 101 全景與象山綠意。全棟採用日本住友航太級制震阻尼器與義大利頂級石材立面，為層峰人士度身定制傳世官邸。"
    },
    {
        "id": "horizon",
        "name": "保量・天璽",
        "subtitle": "THE HORIZON MANOR",
        "category": "residence",
        "category_name": "豪宅名邸",
        "status": "全新公開",
        "badge_class": "badge-new",
        "location": "台北市大安區・大安森林公園首排",
        "specs": "85 ~ 130 坪 | 雙併大景四面採光",
        "architect": "日本景觀美學大師工藝",
        "image": "/static/images/project-lobby.jpg",
        "tag": "公園首席林蔭",
        "description": "座落萬坪森林公園首排，引進自然綠意與微氣候流動系統。以雙層中空 Low-E 靜音工法隔絕城市喧囂，挑高 7 米 8 義大利大理石藝廊迎賓大廳。"
    },
    {
        "id": "botanica",
        "name": "保量・沐光之森",
        "subtitle": "THE BOTANICA VILLA",
        "category": "villa",
        "category_name": "景觀名墅",
        "status": "限量 6 席預約中",
        "badge_class": "badge-vip",
        "location": "台中市七期重劃區・市政綠園道特區",
        "specs": "140 ~ 260 坪 | 獨棟獨院戶戶無邊際泳池",
        "architect": "瑞士純粹極簡建築事務所",
        "image": "/static/images/project-villa.jpg",
        "tag": "頂級私莊名邸",
        "description": "極少數都會核心的獨棟綠洲莊園，融合清水模與溫潤石材。戶戶享有專屬獨立地下私家車庫、私人無邊際鏡面泳池與星空景觀露台。"
    },
    {
        "id": "skyline",
        "name": "保量・天際匯",
        "subtitle": "THE SKYLINE TOWER",
        "category": "commercial",
        "category_name": "商務地標",
        "status": "即將落成",
        "badge_class": "badge-soon",
        "location": "台北市南港經貿園區・捷運站出口直通",
        "specs": "75 ~ 320 坪 | 彈性挑高國際商務樓層",
        "architect": "英倫永續綠建築團隊",
        "image": "/static/images/hero-building.jpg",
        "tag": "黃金級綠建築",
        "description": "新世代企業全球總部首選，榮獲美國 LEED 黃金級綠建築認證。搭載 AI 節能換氣與智慧人臉迎賓系統，彰顯跨國跨時代的企業威望。"
    }
]

@app.route("/")
def index():
    """首頁：渲染保量建設頂級奢華官方首頁"""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return render_template(
        "index.html",
        current_time=current_time,
        projects=PROJECTS,
        total_projects=len(PROJECTS)
    )

@app.route("/api/projects", methods=["GET"])
def api_projects():
    """提供建案列表與分類過濾 API"""
    category = request.args.get("category", "all")
    if category == "all":
        filtered = PROJECTS
    else:
        filtered = [p for p in PROJECTS if p["category"] == category]
    return jsonify({
        "status": "success",
        "count": len(filtered),
        "data": filtered
    })

@app.route("/api/appointment", methods=["POST"])
def api_appointment():
    """線上 VIP 預約賞屋表單提交 API"""
    data = request.get_json(silent=True) or request.form.to_dict()
    
    if not data:
        return jsonify({
            "status": "error",
            "message": "請提供預約資料"
        }), 400

    name = data.get("name", "").strip()
    gender = data.get("gender", "先生").strip()
    phone = data.get("phone", "").strip()
    email = data.get("email", "").strip()
    project = data.get("project", "").strip()
    visit_date = data.get("date", "").strip()
    time_slot = data.get("time_slot", "").strip()
    budget = data.get("budget", "").strip()
    notes = data.get("notes", "").strip()

    # 驗證必填欄位
    errors = []
    if not name or len(name) < 2:
        errors.append("請填寫貴賓姓名（至少 2 個字元）")
    if not phone or not re.match(r"^09\d{8}$", re.sub(r"[\s\-]", "", phone)):
        errors.append("請填寫正確的手機號碼（格式如：0912-345-678）")
    if not project:
        errors.append("請選擇欲預約鑑賞之建案")
    if not visit_date:
        errors.append("請選擇預約日期")
    if not time_slot:
        errors.append("請選擇偏好時段")

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
        "email": email,
        "project": project,
        "date": visit_date,
        "time_slot": time_slot,
        "budget": budget,
        "notes": notes,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    APPOINTMENTS.append(record)

    return jsonify({
        "status": "success",
        "message": f"尊榮貴賓 {name} {gender}，您好！您的預約已成功受理。",
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
    """提供前端測試與相容性使用的 API"""
    return jsonify({
        "status": "success",
        "message": "來自 Flask 後端的問候：Hello,達喻大帥哥! 保量建設",
        "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

if __name__ == "__main__":
    print("保量建設官方網站伺服器正在啟動...")
    print("請在瀏覽器開啟: http://127.0.0.1:5000")
    app.run(debug=True, host="127.0.0.1", port=5000)
