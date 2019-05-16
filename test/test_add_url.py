import requests

from requests_toolbelt import MultipartEncoder

m = MultipartEncoder(
        fields={'video_url':'http://192.168.0.108/15564515795300.mp4'}
        )
res = requests.post('http://172.17.0.1:7051/v1/video',data=m, headers={'Content-Type': m.content_type})
print(res.text)