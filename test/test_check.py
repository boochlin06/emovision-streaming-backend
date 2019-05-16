import urllib3
import sys
import requests
url = "http://172.17.0.1:7051/v1/video/"+sys.argv[1]
r = requests.get(url)
print(r.status_code)
print(r.text)