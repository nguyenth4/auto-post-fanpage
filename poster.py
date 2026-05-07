import requests
import datetime

# don't change this!
#fanpageID = 1549950165266687
import requests
import pyexcel
import json
import os
from dotenv import load_dotenv

load_dotenv()

def run_auto_post():
    # Supabase setup
    SUPABASE_URL = os.environ.get('SUPABASE_URL')
    SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
    fanpageID = '932826203256993'
    token = ''

    if SUPABASE_URL and SUPABASE_KEY:
        try:
            url = f"{SUPABASE_URL}/rest/v1/app_config?id=eq.1"
            headers = {
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json"
            }
            response = requests.get(url, headers=headers)
            if response.status_code == 200 and response.json():
                config = response.json()[0]
                fanpageID = config.get('fanpage_id', fanpageID)
                token = config.get('access_token', '')
        except Exception as e:
            print(f"Lỗi khi lấy cấu hình từ Supabase API: {e}")
    else:
        # Fallback to local file
        try:
            with open('config.json', 'r') as f:
                config = json.load(f)
                fanpageID = config.get('fanpageID', fanpageID)
                token = config.get('token', '')
        except FileNotFoundError:
            pass

    apiUrl = 'https://graph.facebook.com/'+fanpageID+'/feed?'
    
    import pyexcel as pe
    try:
        records = pe.iget_records(file_name="content.xlsx")
        output = []
        for record in records:
            if not record.get('Message') and not record.get('Image'):
                continue
                
            date = convertTime(record['Year'],record['Month'],record['Day'],record['Hour'],record['Minute'],record['Second'])
            date = int(date)
            
            image_name = record.get('Image')
            result = Post(apiUrl, token, record['Message'], date, image_name)
            output.append(result)
        return "\n".join(output)
    except Exception as e:
        return f"Lỗi khi đọc file Excel: {str(e)}"

# Update Post function to return string instead of print
def Post(apiUrl, token, message, time, image_name=None):
    status_msg = ""
    if image_name:
        photo_url = apiUrl.replace('/feed?', '/photos?')
        image_path = os.path.join('images', image_name)
        
        if os.path.exists(image_path):
            with open(image_path, 'rb') as f:
                payload = {
                    'access_token': token,
                    'published': 'false',
                    'caption': message,
                    'scheduled_publish_time': time
                }
                files = {'source': f}
                respond = requests.post(photo_url, data=payload, files=files)
        else:
            image_name = None 
            
    if not image_name:
        payload = {
            'access_token' : token,
            'published' : 'false',
            'message' : message,
            'scheduled_publish_time': time
        }
        respond = requests.post(apiUrl, data=payload)

    if respond.status_code == 200:
        return f"Thành công: {message[:30]}... ({'Ảnh' if image_name else 'Text'}) vào lúc {datetime.datetime.fromtimestamp(time)}"
    else:
        return f"Lỗi: {respond.text}"

def convertTime(year,month,day,hour,minute,second):
    date = datetime.datetime(year,month,day,hour,minute,second)
    return datetime.datetime.timestamp(date)

if __name__ == '__main__':
    print(run_auto_post())

