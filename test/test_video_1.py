
import cv2
import datetime
from multiprocessing import Process,Lock,Pool,Manager
import sys
import urllib.parse
import traceback
import time
import random
def streaming(rtsp):
    try:
        print("Start rtsp1 streaming fetch:",rtsp)
        cap = cv2.VideoCapture(rtsp)
        fps = cap.get(cv2.CAP_PROP_FPS)
        if (fps == 0):
            result[rtsp] = False
            return rtsp,False,0
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
            
            FRAME_NOW = cap.get(cv2.CAP_PROP_POS_FRAMES)  # 当前帧数
            if (FRAME_NOW % fps == 0):
                ret, frame = cap.read()
            else:
                ret = cap.grab()
            timestamp = cap.get(cv2.CAP_PROP_POS_MSEC)
            #videoWriter.write(frame)
            #print("time:",datetime.datetime.now(),",rtsp:",rtsp,',current:', FRAME_NOW,", timestamp",(timestamp/1000),',result:',ret)
            if ret == False:
                print("time:",datetime.datetime.now(),",rtsp:",rtsp,',current:', FRAME_NOW,", timestamp",(timestamp/1000),' ,fail,result:',ret)
            
                result[rtsp] = False
                output_current_result(rtsp,FRAME_NOW)
                return rtsp,False,FRAME_NOW
            else:
                result[rtsp] = True
            if (num_frames != 0 and FRAME_NOW>= num_frames):
                print(rtsp,',finish the task,current_frame:',FRAME_NOW)
                result[rtsp] = True
                output_current_result(rtsp,FRAME_NOW)
                return rtsp,True,FRAME_NOW
            if (FRAME_NOW%200 == 99 and bool(random.getrandbits(1))):
                output_current_result(rtsp,FRAME_NOW)
            
            time.sleep(0.19)
                        
        #videoWriter.release()
        cap.release()
        cv2.destroyAllWindows()
    except:
        result[rtsp] = False
        traceback.print_exc()
        return rtsp,False,FRAME_NOW

def output_current_result(rtsp , current):
    count = len(result)
    fail_count =0
    result_list = list(result.values())
    for i in result_list :
        #artsp_path = urllib.parse.quote(rtsp_list[i])
        #print(rtsp_list[i],",result:",result[i])
        if (i == False):
            fail_count +=1
    print(rtsp,",total :",count,",fail:",fail_count , "fail rate:",(fail_count/count),',current:',current)
    #print(datetime.datetime.now(),result,",current:",current)

argv = sys.argv
with open(argv[1]) as f:
    content = f.readlines()

rtsp_list = [x.strip() for x in content]
manager = Manager()
result = manager.dict()
pool_result = []
pool = Pool(processes = len(rtsp_list))
if __name__ == '__main__' :  
    lock = Lock()
    test_rtsp_count = len(rtsp_list)
    print ("Test streaming pressure, count:",test_rtsp_count)
  
    for i in range(test_rtsp_count) :
        result[rtsp_list[i]] = True
        r = pool.apply_async(streaming,(rtsp_list[i],))
        pool_result.append(r)

    pool.close()#　關閉進程池,不再接受請求
    pool.join() # 等待進程池中的事件執行完畢，回收進程池
    fail_count = 0
    for r in pool_result:
        path , res , final_frame = r.get()
        if res == False:
            fail_count +=1
        print("return:",path,",res:",res , ",final frame:",final_frame) 
    print ("Process end. count:",len(result), ",fail count:",r.get()," fail_rate:",(fail_count/len(result)))
    output_current_result("","")
