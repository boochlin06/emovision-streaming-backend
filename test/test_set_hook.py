import requests

from requests_toolbelt import MultipartEncoder

m = MultipartEncoder(
        fields={'webhook':'http://172.17.0.1:7051/v1/video/webhook/test'}
        )
res = requests.post('http://172.17.0.1:7051/v1/video/webhook/',data=m, headers={'Content-Type': m.content_type})
print(res.text)