import requests

from requests_toolbelt import MultipartEncoder

m = MultipartEncoder(
        fields={'webhook':'http://192.168.0.111:7051/v1/video/webhook/test'}
        )
res = requests.post('http://192.168.0.111:7051/v1/video/webhook/',data=m, headers={'Content-Type': m.content_type})
print(res.text)