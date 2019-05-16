import requests

from requests_toolbelt import MultipartEncoder

f = open('bocom1.mp4', 'rb')
m = MultipartEncoder(
        fields={'video_file':('bocom1.mp4',f)
                ,'output_json':'0'}
        )
res = requests.post('http://172.17.0.1:7051/v1/video',data=m, headers={'Content-Type': m.content_type})
print(res.text)