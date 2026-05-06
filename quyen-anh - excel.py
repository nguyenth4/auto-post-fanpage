import requests
import datetime

# don't change this!
#fanpageID = 1549950165266687
import json

# Load config
try:
    with open('config.json', 'r') as f:
        config = json.load(f)
        fanpageID = config.get('fanpageID', '932826203256993')
        token = config.get('token', '')
except FileNotFoundError:
    fanpageID = '932826203256993'
    token = ''

apiUrl = 'https://graph.facebook.com/'+fanpageID+'/feed?'

# your content
message = 'This is 8h40 post';

# your time
#time = 1453389600;


import os

def Post(apiUrl, token, message, time, image_name=None):
    # If there's an image, use /photos endpoint, otherwise use /feed
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
                files = {
                    'source': f
                }
                respond = requests.post(photo_url, data=payload, files=files)
        else:
            print(f"Image not found: {image_path}, skipping image.")
            image_name = None # Fallback to feed post
            
    if not image_name:
        payload = {
            'access_token' : token,
            'published' : 'false',
            'message' : message,
            'scheduled_publish_time': time
        }
        respond = requests.post(apiUrl, data=payload)

    if respond.status_code == 200:
        print(f"Post successful ({'Photo' if image_name else 'Text'})")
        print("post date ", datetime.datetime.fromtimestamp(time))
    else:
        print(respond.content)

def convertTime(year,month,day,hour,minute,second):
    date = datetime.datetime(year,month,day,hour,minute,second)
    return datetime.datetime.timestamp(date)

import pyexcel as pe
records = pe.iget_records(file_name="content.xlsx") #import from excel file
for record in records: # for line by lines in sheet
    if not record.get('Message') and not record.get('Image'):
        continue
        
    date = convertTime(record['Year'],record['Month'],record['Day'],record['Hour'],record['Minute'],record['Second'])
    date = int(date)
    
    # Get image from excel if it exists
    image_name = record.get('Image')
    Post(apiUrl, token, record['Message'], date, image_name)

