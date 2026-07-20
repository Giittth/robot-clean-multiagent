import requests
import json

url = "http://127.0.0.1:8000/chat/?stream=true"
payload = {"user_id": 0, "kb_id": 1, "message": "你好"}
response = requests.post(url, json=payload, stream=True)
for line in response.iter_lines():
    if line:
        print(line.decode('utf-8'))