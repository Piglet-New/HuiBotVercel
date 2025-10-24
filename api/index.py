from flask import Flask, jsonify

app = Flask(__name__)

@app.get("/api/healthz")
def healthz():
    return jsonify({"ok": True, "msg": "online"})

@app.get("/api/")
def root():
    return jsonify({"ok": True})
