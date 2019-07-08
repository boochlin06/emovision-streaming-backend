
import cv2
import datetime
from multiprocessing import Process,Lock
import sys
import urllib.parse
import traceback
import time

#'rtsp://admin:admin123@192.168.0.119:554/cam/playback?channel=88&subtype=0&starttime=2019_06_12_08_10_00&endtime=2019_06_12_08_55_00'
def streaming(rtsp,lock):
    try:
        print("Start rtsp1 streaming fetch:",rtsp)
        cap = cv2.VideoCapture(rtsp)
        fps = cap.get(cv2.CAP_PROP_FPS)
        if (fps == 0):
            result[rtsp] = False
            return
        print("Frames per second using video.get(cv2.CAP_PROP_FPS) : {0}".format(fps))
        num_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        print('共有', num_frames, '帧')
        frame_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        frame_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        print('高：', frame_height, '宽：', frame_width)

        FRAME_NOW = cap.get(cv2.CAP_PROP_POS_FRAMES)  # 第0帧
        # outputName="output.mp4"
        #fourcc = cv2.VideoWriter_fourcc('m','p','4','v')
        # videoWriter = cv2.VideoWriter(outputName,int(fourcc), fps,(int(frame_width),int(frame_height)),True)
        while True:
            lock.acquire()
            try:
                FRAME_NOW = cap.get(cv2.CAP_PROP_POS_FRAMES)  # 当前帧数
                if (FRAME_NOW % fps == 0):
                    ret, frame = cap.read()
                else:
                    ret = cap.grab()
                timestamp = cap.get(cv2.CAP_PROP_POS_MSEC)
                #videoWriter.write(frame)
                print("time:",datetime.datetime.now(),",rtsp:",rtsp,',current:', FRAME_NOW,", timestamp",(timestamp/1000),',result:',ret)
                if ret == False:
                    result[rtsp] = False
                    output_current_result(rtsp,FRAME_NOW)
                    break
                else:
                    result[rtsp] = True
                if (num_frames != 0 and FRAME_NOW>= num_frames):
                    print(rtsp,',finish the task,current_frame:',FRAME_NOW)
                    result[rtsp] = True
                    output_current_result(rtsp,FRAME_NOW)
                    break
                if (FRAME_NOW%100 == 0):
                    output_current_result(rtsp,FRAME_NOW)
            finally:
                #pass
                lock.release()
            time.sleep(0.1)
                        
        #videoWriter.release()
        cap.release()
        cv2.destroyAllWindows()
    except:
        result[rtsp] = False
        traceback.print_exc()

def output_current_result(rtsp , current):
    count = len(result)
    fail_count =0
    for i in range(count) :
        #artsp_path = urllib.parse.quote(rtsp_list[i])
        print(rtsp_list[i],",result:",result[rtsp_list[i]])
        if (result[rtsp_list[i]] == False):
            fail_count +=1
    print(rtsp,",total :",count,",fail:",fail_count , "fail rate:",(fail_count/count),',current:',current)
    #print(result)

argv = sys.argv
with open(argv[1]) as f:
    content = f.readlines()

rtsp_list = [x.strip() for x in content]
result = {}
pool_result = []
if __name__ == '__main__' :  
  lock = Lock()
  test_rtsp_count = len(rtsp_list)
  print ("Test streaming pressure, count:",test_rtsp_count)
  numList = [] 
  
  for i in range(test_rtsp_count) :
    rtsp_path = urllib.parse.quote(rtsp_list[i])
    result[rtsp_list[i]] = True
    
    p = Process(target=streaming, args=(rtsp_list[i],lock,))  
    numList.append(p)
    p.start()  
    #p.join()
  for i in range(test_rtsp_count):
      numList[i].join()
  print ("Process end. count:",len(result))
  output_current_result("","")
