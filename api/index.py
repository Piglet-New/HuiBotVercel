# /api/index.py
from flask import Flask, jsonify
from api.routes.health import bp as health_bp
from api.routes.webhook import bp as webhook_bp

app = Flask(__name__)

# Trang gốc /api/
@app.get("/api/")
def root():
    return jsonify({"ok": True, "service": "hui-bot", "msg": "ready"})

# Mount các blueprint vào prefix /api
app.register_blueprint(health_bp, url_prefix="/api")
app.register_blueprint(webhook_bp, url_prefix="/api")
