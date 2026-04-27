from flask import Flask
from threading import Thread
import os

app = Flask('')

@app.route('/')
def home():
    return "OK", 200

def run():
    # Render等の環境に合わせてポートを設定
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()
