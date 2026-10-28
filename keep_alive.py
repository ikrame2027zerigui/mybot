import os
from flask import Flask, send_file, request, jsonify
from threading import Thread

app = Flask(__name__)

# استدعاء دالة المعالجة المباشرة من البوت
_action_callback = None

def register_action_callback(cb):
    global _action_callback
    _action_callback = cb

@app.route('/')
def home():
    index_path = os.path.join(os.path.dirname(__file__), 'index.html')
    if os.path.exists(index_path):
        return send_file(index_path)
    return "Bot is alive 24/7!"

@app.route('/menu')
@app.route('/webapp')
def menu():
    index_path = os.path.join(os.path.dirname(__file__), 'index.html')
    if os.path.exists(index_path):
        return send_file(index_path)
    return "Bot is alive 24/7!"

@app.route('/api/action', methods=['POST'])
def handle_api_action():
    try:
        data = request.get_json(force=True, silent=True) or {}
        user_id = data.get("user_id")
        action = data.get("action")
        if user_id and action and _action_callback:
            _action_callback(user_id, action)
            return jsonify({"status": "ok", "action": action})
    except Exception as e:
        print("API action notice:", e)
    return jsonify({"status": "error"}), 400

@app.route('/healthz')
@app.route('/ping')
def ping():
    return "OK", 200

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, use_reloader=False)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()
