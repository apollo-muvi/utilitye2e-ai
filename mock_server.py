"""
Mock Admin Panel Server - Universal Admin Panel (Generic)

Three core modules (domain-independent):
1. Users (用戶管理) - CRUD + role + status
2. Settings (系統設定) - Form sections + save/apply
3. Logs (日誌查看) - Read-only + filters + pagination
"""

from flask import Flask, render_template, request, jsonify

app = Flask(__name__, template_folder='.')

# Mock database
users = [
    {"id": 1, "username": "admin", "email": "admin@example.com", "role": "admin", "status": "active"},
    {"id": 2, "username": "user1", "email": "user1@example.com", "role": "user", "status": "active"},
    {"id": 3, "username": "user2", "email": "user2@example.com", "role": "guest", "status": "inactive"},
]

settings = {
    "site_name": "My Admin Panel",
    "max_users": 100,
    "enable_registration": True,
    "session_timeout": 30,
    "allowed_ips": "192.168.1.0/24,10.0.0.0/8"
}

logs = [
    {"id": 1, "timestamp": "2026-07-25 10:30:00", "user": "admin", "action": "login", "ip": "192.168.1.100", "status": "success"},
    {"id": 2, "timestamp": "2026-07-25 10:31:00", "user": "admin", "action": "update_settings", "ip": "192.168.1.100", "status": "success"},
    {"id": 3, "timestamp": "2026-07-25 10:32:00", "user": "user1", "action": "login_failed", "ip": "192.168.1.101", "status": "failed"},
    {"id": 4, "timestamp": "2026-07-25 10:33:00", "user": "admin", "action": "create_user", "ip": "192.168.1.100", "status": "success"},
    {"id": 5, "timestamp": "2026-07-25 10:34:00", "user": "user2", "action": "logout", "ip": "192.168.1.102", "status": "success"},
]

next_user_id = 4
next_log_id = 6

# Routes
@app.route('/')
def index():
    return render_template('mock_admin.html', current_page='users', users=users, settings=settings, logs=logs)

@app.route('/page/<page_name>')
def page(page_name):
    return render_template('mock_admin.html', current_page=page_name, users=users, settings=settings, logs=logs)

# Users API
@app.route('/api/users', methods=['GET'])
def list_users():
    return jsonify({"data": users})

@app.route('/api/users', methods=['POST'])
def add_user():
    global next_user_id
    data = request.json
    new_user = {
        "id": next_user_id,
        "username": data.get("username", ""),
        "email": data.get("email", ""),
        "role": data.get("role", "user"),
        "status": data.get("status", "active")
    }
    users.append(new_user)
    next_user_id += 1
    return jsonify({"success": True, "data": new_user})

@app.route('/api/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    data = request.json
    for u in users:
        if u["id"] == user_id:
            u.update({
                "username": data.get("username", u["username"]),
                "email": data.get("email", u["email"]),
                "role": data.get("role", u["role"]),
                "status": data.get("status", u["status"])
            })
            return jsonify({"success": True, "data": u})
    return jsonify({"error": "Not found"}), 404

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    global users
    users = [u for u in users if u["id"] != user_id]
    return jsonify({"success": True})

@app.route('/api/users/<int:user_id>/toggle', methods=['POST'])
def toggle_user_status(user_id):
    for u in users:
        if u["id"] == user_id:
            u["status"] = "inactive" if u["status"] == "active" else "active"
            return jsonify({"success": True, "data": u})
    return jsonify({"error": "Not found"}), 404

# Settings API
@app.route('/api/settings', methods=['GET'])
def get_settings():
    return jsonify({"data": settings})

@app.route('/api/settings', methods=['POST'])
def save_settings():
    global settings
    data = request.json
    settings.update(data)
    return jsonify({"success": True, "data": settings})

# Logs API
@app.route('/api/logs', methods=['GET'])
def list_logs():
    log_type = request.args.get('type', '')
    filtered = logs
    if log_type:
        filtered = [l for l in logs if l['action'] == log_type]
    return jsonify({"data": filtered, "total": len(filtered)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3002, debug=True)
