import urllib3
import sys
from http.client import responses
http = urllib3.PoolManager()
r = http.request('GET', 'http://192.168.0.108:7051/v1/video/download/video/'+sys.argv[1], preload_content=False)
if r.status == 200:
    with open("testdownload.mp4", 'wb') as out:
        while True:
            data = r.read(4096)
            if not data:
                break
            out.write(data)

    r.release_conn()
else:
    print("download video fail:"+responses[r.status])

# r = http.request('GET', 'http://172.17.0.1:7051/v1/video/download/json/'+sys.argv[1], preload_content=False)
# if r.status == 200:
#     with open("testdownload.json", 'wb') as out:
#         while True:
#             data = r.read(4096)
#             if not data:
#                 break
#             out.write(data)

#     r.release_conn()
# else:
#     print("download json fail:"+responses[r.status])