from tornado.ioloop import IOLoop, PeriodicCallback
from tornado import gen
from tornado.websocket import websocket_connect
from tornado import httputil ,httpclient
import urllib.parse
import marshal
import json
import time
import sys

from typing import cast

faceset_token_dict = {
    "02":"b49f2510-925d-11e9-99ce-0242ac140014",
    "04":"fa3f39d2-7572-11e9-95f7-0242ac120013",
    "08":"536adf8a-7568-11e9-999b-0242ac1f0013",
    "11":"3e53d222-755f-11e9-9657-0242ac1b0013",
    "16":"fcfc8d92-8da4-11e9-a707-0242ac130014",
}


argv = sys.argv
if len(argv) != 3:
    print("Usage: python client.py [Server IP(ex: 11)]  [RTSP list file(ex: 1.txt)]")
    exit()

with open(argv[2]) as f:
    content = f.readlines()

rtsp_list = [x.strip() for x in content]

if argv[1] not in faceset_token_dict:
    print("face token of this server ip is not set")
    exit()

start_time_list = [None]*len(rtsp_list)
frame_count_list = [-1]*len(rtsp_list)
end_time_list = [None]*len(rtsp_list)
time_stamp_list = [None]*len(rtsp_list)
face_count_list = [0]*len(rtsp_list)
hands_count_list = [0]*len(rtsp_list)
wonderful_count_list = [0]*len(rtsp_list)


def printLog():
    print("Timestamp:       ", time_stamp_list)
    print("FrameCount:      ", frame_count_list)
    print("FaceAverage:     ", [(round(a/b,1) if b != 0 else 0) for a,b in zip(face_count_list,frame_count_list)])
    print("HandsCount:      ", hands_count_list)
    print("HandsAverage:    ", [(round(a/b,2) if b != 0 else 0) for a,b in zip(hands_count_list,frame_count_list)])
    print("WonderfulCount:  ", wonderful_count_list)
    print("FPS:             ", sum(frame_count_list) / sum(  [(b-a if (b!=None and a!= None and b-a != 0) else 1) for a,b in zip(start_time_list,end_time_list)]))
    

class Client(object):
    def __init__(self, url, timeout,index):
        self.index = index
        self.url = url
        self.timeout = timeout
        self.ws = None
        self.connect()
        self.timer = PeriodicCallback(self.keep_alive, 5000)
        self.timer.start()

    @gen.coroutine
    def connect(self):
        print ("trying to connect")
        try:
            headers = httputil.HTTPHeaders({
                'Accept-Encoding': '',
                'HTTP_ACCEPT_ENCODING': '',
                'Connection': 'upgrade',
                'Upgrade': 'WebSocket',
                'Sec-Websocket-Origin': '*',
            }) 
            request = httpclient.HTTPRequest(url=self.url, headers=headers)  
            self.ws = yield websocket_connect(url=request,compression_options={'compression_level':0})
        except Exception as e:
            print ("connection error")
            print (e)
        else:
            print ("connected")
            self.run()

    @gen.coroutine
    def run(self):
        global start_time_list 
        global frame_count_list 
        global end_time_list 
        global time_stamp_list 
        global face_count_list 
        global hands_count_list 
        global wonderful_count_list 
        # global error_count 
        while True:
            msg = yield self.ws.read_message()

            # object_methods = [method_name for method_name in dir(self.ws)]
            # print(object_methods)
            # print("==headers==")
            # print(self.ws.headers)
            # print("==headers_received==")
            # print(self.ws.get_compression_options())


            if msg is None:
                print ("connection closed",rtsp_list[self.index])
                self.ws.close()
                self.ws = None
                self.timer.stop()
                break
            else:
                data = json.loads(msg)
                i = self.index
                
                if start_time_list[i] == None:
                    start_time_list[i] = time.time()
                frame_count_list[i] += 1
                end_time_list[i] = time.time()
                time_stamp_list[i] = data['time_stamp']
                if 'analyze_result' in data:
                    wonderful_count_list[i] =  wonderful_count_list[i]+ data["analyze_result"]['is_wonderful']  
                    # if data["image_base64"] != "":
                    #     print("=========wonderful!!!===========")
                    # print(data["analyze_result"].keys())
                    # print(data['analyze_result']["hands_up_count"])
                    if 'faces' in data["analyze_result"].keys():
                        face_count_list[i] += len(data['analyze_result']['faces'])
                    if "hands_up_count" in data["analyze_result"].keys():
                        hands_count_list[i] +=  data['analyze_result']["hands_up_count"]
                else:
                    if 'message' in data and data['message'] == 'close':
                        print("======= Connection at index %d was closed. ========" % i)
                # else:
                #     print("no hands_up_count")
 

    def keep_alive(self):
        # if self.index == 0:
        #     printLog()
        if self.ws != None:
            self.ws.write_message("ack")

if __name__ == "__main__":
    for i in range(len(rtsp_list)):
        # IOLoop.current().stop() 
        client = Client("ws://192.168.0.1"+argv[1]+":7080/streaming/video?user_data={id:" + str(i) + ",start_time:1555052213}&feature=FACE&feature=BODY&always_return_image=0&url=" + urllib.parse.quote(rtsp_list[i])+"&faceset_token="+ faceset_token_dict[argv[1]], 60,i)
        # time.sleep(1)
        # IOLoop.current().start() 
        # time.sleep(1)

    PeriodicCallback(printLog, 5000).start()
    IOLoop.current().start() 