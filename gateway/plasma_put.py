import cv2
import pyarrow.plasma as plasma
import os
import base64
img = cv2.imread("000425.jpg",cv2.IMREAD_UNCHANGED)
client = plasma.connect(os.environ['PLASMA_PATH'], "", 0)
# print(os.environ['PLASMA_PATH'])


# tmp = client.put('test in plasma')
# res = client.get(tmp)
# print(res)

item = client.put(img)
plasma_id = item.binary()
# print(item)
# print(plasma_id)
print(base64.b64encode(plasma_id).decode('utf-8'))


image = client.get(item)
print(image.shape)
# [img2] = client.get_buffers([item])
# img2 = client.get(plasma_id)
# client.delete([plasma_id])