import urllib3
import sys
import requests
import json
url = "http://192.168.0.108:7051/v1/videos"
r = requests.get(url)
print(r.status_code)
# print(r.text)
datas = json.loads(r.text)
tasks = datas["task"]


for task in tasks:
    if (task['state'] == 'ERROR' or task["input_video"] == "http://192.168.0.108/h264.mp4" or task["input_video"] == "http://192.168.0.108/h264003.mp4"\
    or task["input_video"] == "http://192.168.0.108/h265003.mp4"):
        print(task)
        if (task['state'] == 'ERROR'):
            durl = "http://192.168.0.108:7051/v1/video/"+task["task_id"]
            dr = requests.delete(durl)
            print(dr.status_code)
            print(dr.text)
        

# url = "http://192.168.0.108:7051/v1/video/"+"1c7876f0-1e4c-449f-af4d-c4587ce4f8bc"
# r = requests.delete(url)
# print(r.status_code)
# print(r.text)