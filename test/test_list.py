import sys
import requests
url = "http://192.168.0.111:7051/v1/videos"
r = requests.get(url)
print(r.status_code)
print(r.text)