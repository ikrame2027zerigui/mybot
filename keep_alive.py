import os
from flask import Flask, send_file
from threading import Thread

app = Flask(__name__)

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
