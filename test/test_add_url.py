import requests

from requests_toolbelt import MultipartEncoder

m = MultipartEncoder(
        fields={'video_url':'http://192.168.0.108/h264.mp4'}
        )
res = requests.post('http://192.168.0.108:7051/v1/video',data=m, headers={'Content-Type': m.content_type})
print(res.text)
# m = MultipartEncoder(
#         fields={'video_url':'http://192.168.0.108/h265003.mp4'}
#         )
# res = requests.post('http://192.168.0.111:7051/v1/video',data=m, headers={'Content-Type': m.content_type})
# print(res.text)
# m = MultipartEncoder(
#         fields={'video_url':'http://192.168.0.108/155956728211880.mp4'}
#         )
# res = requests.post('http://192.168.0.111:7051/v1/video',data=m, headers={'Content-Type': m.content_type})
# print(res.text)
# m = MultipartEncoder(
#         fields={'video_url':'http://192.168.0.108/155956728211880.mp4'}
#         )
# res = requests.post('http://192.168.0.108:7051/v1/video',data=m, headers={'Content-Type': m.content_type})
# print(res.text)
# m = MultipartEncoder(
#         fields={'video_url':'http://192.168.0.108/155956728211880.mp4'}
#         )
# res = requests.post('http://192.168.0.108:7051/v1/video',data=m, headers={'Content-Type': m.content_type})
# print(res.text)