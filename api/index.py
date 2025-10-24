from flask import Flask, jsonify

app = Flask(__name__)

@app.get("/api/healthz")
def healthz():
    return jsonify({"ok": True, "msg": "online"})

@app.get("/api/")
def root():
    return jsonify({"ok": True})

# Tạm thời chưa import DB và adapter
# from db_pg import init_db
# from adapter_huibot import handle_update
