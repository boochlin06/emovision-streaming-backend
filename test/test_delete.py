import urllib3
import sys
import requests
url = "http://192.168.0.111:7051/v1/video/"+sys.argv[1]
r = requests.delete(url)
print(r.status_code)
print(r.text)