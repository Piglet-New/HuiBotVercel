import os
from flask import Flask, jsonify
from api.routes.health import bp as health_bp
from api.routes.webhook import bp as webhook_bp
from api.routes.test import bp as test_bp

app = Flask(__name__)
app.register_blueprint(health_bp, url_prefix="/api")
app.register_blueprint(webhook_bp, url_prefix="/api")
app.register_blueprint(test_bp, url_prefix="/api")

@app.get("/api/")
def root():
    return jsonify({"ok": True, "msg": "API online"})
