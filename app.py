import os
import json
import subprocess
import requests
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

CONFIG_FILE = 'config.json'

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {"fanpageID": "", "token": ""}

def save_config(data):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(data, f, indent=4)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/config', methods=['GET', 'POST'])
def config():
    if request.method == 'POST':
        data = request.json
        fanpage_id = data.get('fanpageID')
        token = data.get('token')
        
        # Validate ID and Token before saving
        if not fanpage_id or not token:
            return jsonify({"status": "error", "message": "Vui lòng nhập đầy đủ ID và Token"}), 400
            
        try:
            # Check if token is valid for this fanpageID
            validation_url = f'https://graph.facebook.com/v19.0/{fanpage_id}?fields=id,name&access_token={token}'
            response = requests.get(validation_url)
            val_data = response.json()
            
            if response.status_code != 200:
                error_msg = val_data.get('error', {}).get('message', 'Token hoặc ID không hợp lệ')
                return jsonify({"status": "error", "message": f"Facebook báo lỗi: {error_msg}"}), 400
            
            # If everything is ok, save it
            save_config(data)
            return jsonify({
                "status": "success", 
                "message": f"Kết nối thành công tới Fanpage: {val_data.get('name')}"
            })
            
        except Exception as e:
            return jsonify({"status": "error", "message": f"Lỗi hệ thống khi xác thực: {str(e)}"}), 500
            
    return jsonify(load_config())

@app.route('/api/run_script', methods=['POST'])
def run_script():
    try:
        # Run the python script
        # Assuming the python executable is available
        python_path = os.path.join('.venv', 'Scripts', 'python.exe')
        if not os.path.exists(python_path):
            python_path = 'python' # Fallback
            
        result = subprocess.run([python_path, 'quyen-anh - excel.py'], 
                              capture_output=True, text=True, cwd=os.getcwd())
        
        return jsonify({
            "status": "success" if result.returncode == 0 else "error",
            "output": result.stdout,
            "error": result.stderr
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/scheduled_posts', methods=['GET'])
def get_scheduled_posts():
    cfg = load_config()
    token = cfg.get('token')
    fanpageID = cfg.get('fanpageID')
    
    if not token or not fanpageID:
        return jsonify({"status": "error", "message": "Thiếu cấu hình Token hoặc ID Fanpage"}), 400
        
    url = f'https://graph.facebook.com/v19.0/{fanpageID}/scheduled_posts?fields=id,message,created_time,scheduled_publish_time,attachments&access_token={token}'
    try:
        response = requests.get(url)
        data = response.json()
        if 'data' in data:
            return jsonify({"status": "success", "posts": data['data']})
        else:
            return jsonify({"status": "error", "message": str(data)}), 400
    except Exception as e:
         return jsonify({"status": "error", "message": str(e)}), 500
         
@app.route('/api/scheduled_posts/<post_id>', methods=['DELETE'])
def delete_post(post_id):
    cfg = load_config()
    token = cfg.get('token')
    
    url = f'https://graph.facebook.com/{post_id}?access_token={token}'
    try:
        response = requests.delete(url)
        if response.status_code == 200:
            return jsonify({"status": "success", "message": "Đã xoá bài viết thành công"})
        else:
            return jsonify({"status": "error", "message": response.text}), 400
    except Exception as e:
         return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
