
import cv2

import datetime
cap = cv2.VideoCapture('rtsp://admin:admin123@192.168.0.119:554/cam/playback?channel=88&subtype=0&starttime=2019_06_12_08_10_00&endtime=2019_06_12_08_55_00')
# cap = cv2.VideoCapture('output.avi')
# cap = cv2.VideoCapture('Minions_banana.mp4')


# 帧率
fps = cap.get(cv2.CAP_PROP_FPS)  # 25.0
print("Frames per second using video.get(cv2.CAP_PROP_FPS) : {0}".format(fps))
# 总共有多少帧
num_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
print('共有', num_frames, '帧')
frame_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
frame_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
print('高：', frame_height, '宽：', frame_width)

FRAME_NOW = cap.get(cv2.CAP_PROP_POS_FRAMES)  # 第0帧
print('当前帧数', FRAME_NOW)  # 当前帧数 0.0
# 读取指定帧,对视频文件才有效，对摄像头无效？？
# frame_no = 500
# cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)  # Where frame_no is the frame you want
# ret, frame = cap.read()  # Read the frame
outputName="output.mp4"
FRAME_NOW = cap.get(cv2.CAP_PROP_POS_FRAMES)
print('当前帧数', FRAME_NOW)  # 当前帧数 122.0
fourcc = cv2.VideoWriter_fourcc('m','p','4','v')
# videoWriter = cv2.VideoWriter(outputName,int(fourcc), fps,(int(frame_width),int(frame_height)),True)
while True:
    ret, frame = cap.read()
    FRAME_NOW = cap.get(cv2.CAP_PROP_POS_FRAMES)  # 当前帧数
    fps = cap.get(cv2.CAP_PROP_FPS)
    timestamp = cap.get(cv2.CAP_PROP_POS_MSEC)
    #videoWriter.write(frame)
    print("time:",datetime.datetime.now(),',当前帧数', FRAME_NOW,",fps:",fps,", timestamp",(timestamp/1000),',result:',ret)

#videoWriter.release()
cap.release()
cv2.destroyAllWindows()