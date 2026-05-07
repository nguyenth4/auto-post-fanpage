import os
import json
import requests
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Supabase setup
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

def get_supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

def load_config():
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            url = f"{SUPABASE_URL}/rest/v1/app_config?id=eq.1"
            response = requests.get(url, headers=get_supabase_headers())
            if response.status_code == 200 and response.json():
                config = response.json()[0]
                return {
                    "fanpageID": config.get('fanpage_id', ''),
                    "token": config.get('access_token', '')
                }
        except Exception as e:
            print(f"Error loading from Supabase API: {e}")
    
    # Fallback to local file only if NOT on Vercel
    if not os.environ.get('VERCEL'):
        if os.path.exists('config.json'):
            with open('config.json', 'r') as f:
                return json.load(f)
    return {"fanpageID": "932826203256993", "token": ""}

def save_config(data):
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            url = f"{SUPABASE_URL}/rest/v1/app_config"
            payload = {
                "id": 1,
                "fanpage_id": data.get('fanpageID'),
                "access_token": data.get('token'),
                "updated_at": "now()"
            }
            response = requests.post(url, headers=get_supabase_headers(), json=payload)
            if response.status_code in [200, 201]:
                return True
            else:
                raise Exception(f"Supabase API Error: {response.text}")
        except Exception as e:
            print(f"Error saving to Supabase API: {e}")
            if os.environ.get('VERCEL'):
                raise Exception(f"Không thể lưu vào Database: {str(e)}")
            
    # Fallback to local file only if NOT on Vercel
    if not os.environ.get('VERCEL'):
        with open('config.json', 'w') as f:
            json.dump(data, f, indent=4)
        return True
    
    raise Exception("Chưa cấu hình Supabase trên Vercel")
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/config', methods=['GET', 'POST'])
def config():
    if request.method == 'POST':
        data = request.json
        fanpage_id = data.get('fanpageID')
        token = data.get('token')
        
        if not fanpage_id or not token:
            return jsonify({"status": "error", "message": "Vui lòng nhập đầy đủ ID và Token"}), 400
            
        try:
            validation_url = f'https://graph.facebook.com/v19.0/{fanpage_id}?fields=id,name&access_token={token}'
            response = requests.get(validation_url)
            val_data = response.json()
            
            if response.status_code != 200:
                error_msg = val_data.get('error', {}).get('message', 'Token hoặc ID không hợp lệ')
                return jsonify({"status": "error", "message": f"Facebook báo lỗi: {error_msg}"}), 400
            
            save_config(data)
            return jsonify({
                "status": "success", 
                "message": f"Kết nối thành công tới Fanpage: {val_data.get('name')}"
            })
            
        except Exception as e:
            return jsonify({"status": "error", "message": f"Lỗi hệ thống: {str(e)}"}), 500
            
    return jsonify(load_config())

import poster

@app.route('/api/run_script', methods=['POST'])
def run_script():
    try:
        # Run the auto post logic directly
        output = poster.run_auto_post()
        
        return jsonify({
            "status": "success" if "Thành công" in output else "error",
            "output": output,
            "error": "" if "Thành công" in output else output
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
