from flask import Flask, render_template, jsonify
from datetime import datetime

app = Flask(__name__)

@app.route("/")
def index():
    # 首頁：渲染單頁式 Hello World
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return render_template("index.html", current_time=current_time)

@app.route("/api/greet", methods=["GET"])
def api_greet():
    # 提供前端非同步互動用的簡易 API
    return jsonify({
        "status": "success",
        "message": "來自 Flask 後端的問候：Hello, World!",
        "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

if __name__ == "__main__":
    # 啟動本機開發伺服器，預設監聽在 http://127.0.0.1:5000
    print("Flask 伺服器正在啟動...")
    print("請在瀏覽器開啟: http://127.0.0.1:5000")
    app.run(debug=True, host="127.0.0.1", port=5000)
