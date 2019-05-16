import base64
import datetime
import json

import grequests
import logging
import cv2
from flask import Flask, Response, redirect, render_template, url_for
from flask_uwsgi_websocket import GeventWebSocket
from requests_toolbelt import MultipartEncoder
import gevent
from gevent.queue import Queue
import traceback
import time
import pyarrow.plasma as plasma
from importlib import import_module
from urllib.parse import parse_qsl
from urllib.parse import parse_qs
from gevent import Timeout
import configparser
import requests
import os
import sys

app = Flask(__name__)
websocket = GeventWebSocket(app)
config = configparser.ConfigParser()
config.read(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'config', 'analyze.ini'))
workerNume = int(config['DEFAULT']['workerNume'])
requestFrameFps = float(config['DEFAULT']['requestFrameFps'])
rtspFrameBuffer = float(config['DEFAULT']['rtspFrameBuffer'])
analyzeAddress=config.get('DEFAULT','analyzeAddress')
handshakeBufferTime = float(config['DEFAULT']['handshakeBufferTime'])
timeOutLimit = float(config['DEFAULT']['timeOutLimit'])
plasmaPath = config.get('DEFAULT','plasmaPath')

# try:
#     import http.client as http_client
# except ImportError:
#     # Python 2
#     import httplib as http_client
# http_client.HTTPConnection.debuglevel = 2

# logging.basicConfig(format='%(asctime)s.%(msecs)03d %(levelname)s {%(module)s} [%(funcName)s] %(message)s'
# , datefmt='%Y-%m-%d,%H:%M:%S', level=logging.INFO)
# logging.getLogger().setLevel(logging.DEBUG)
# requests_log = logging.getLogger("requests")
# requests_log.setLevel(logging.DEBUG)
# requests_log.propagate = True

q = Queue()

def millis():
    return int(round(time.time() * 1000))

@app.route('/ws/bunny')
def index():
    return render_template('ws-test-local-bunny.html')

@app.route('/ws')
def index_ws():
    return render_template('ws-test.html')
@app.route('/ws/c1')
def index_c1():
    return render_template('ws-test-shushin.html')
@app.route('/ws/local')
def index_ws_local():
    return render_template('ws-test-local.html')

@websocket.route('/streaming/check')
def check_status(ws):
    ws.close()
    return "ok",200


@websocket.route('/streaming/video')
def streaming(ws):
    query = dict(parse_qsl(ws.environ['QUERY_STRING']))
    try:
        if query['url'] is None:
            ws.close()
            return
        query['feature']
        query['always_return_image']
        query['user_data']
    except Exception as e:
        print (e)
        ws.close()
        return
    print('time:',datetime.datetime.now(),'rtsp path:',query['url'],'user_data:',query['user_data'] , ',analyze address:',analyzeAddress,',plasmaPath:',plasmaPath)
    comsumerJobs = [gevent.spawn(consumer,i) for i in range(int(workerNume))]
    allJobs = comsumerJobs
    allJobs.append(gevent.spawn(svaeVideoFrame,ws))
    gevent.joinall(allJobs)

def consumer(id):
    print(id,'time:',datetime.datetime.now(),'start  consumer,',id)
    while True:
        if (q.qsize()==0):
            gevent.sleep(0)
        try:
            # print(id,'time:',datetime.datetime.now(),'start to get data consumer,',id,'q size:',q.qsize())
            analyzeItem = q.get()
            if (analyzeItem.ws.connected == False):
                while (q.qsize()>0):
                    q.get()
                break
            # print(analyzeItem.ws.id[:7],'time:',datetime.datetime.now(),',consumer ',id,'cosume:',analyzeItem.plasmaId,",q size:",q.qsize())
            analyze(analyzeItem.buffer,analyzeItem.plasmaId,analyzeItem.ws,analyzeItem.timeStamp)
        except Exception as e:
            gevent.sleep(0)
            print(e)
    print(analyzeItem.ws.id[:7],'time:',datetime.datetime.now(),'close consumer,',id)


class AnalyzeItem():
    def __init__(self, buffer, plasmaId, ws, item ,timeStamp):
        self.buffer = buffer
        self.plasmaId = plasmaId
        self.ws = ws
        self.item = item
        self.timeStamp = timeStamp


def svaeVideoFrame(ws):
    query = dict(parse_qsl(ws.environ['QUERY_STRING']))
    # print(ws.environ['QUERY_STRING'])
    try:
        retry =0 
        while(True):
            camera = cv2.VideoCapture(query['url'])    
            if not camera.isOpened():
                retry += 1
                gevent.sleep(10000)
                print('Could not start camera:retry:',retry)
                if (retry>3):
                    raise RuntimeError('Could not start camera.')
            elif (camera.isOpened()):
                break
       
        fps = camera.get(cv2.CAP_PROP_FPS)
        total_frame = camera.get(cv2.CAP_PROP_FRAME_COUNT)

        print(ws.id[:7],'time:',datetime.datetime.now(),'rtsp path:',query['url'],",fps:",fps,",total frame:",total_frame)
        startTime = millis()
        # imgThumb = cv2.imread('benchmark_1080_61.jpg')

        frameCount =0
        frameCountStartTime = millis()
        frameGapTime = 1.0/fps * 1000
        total_frame = camera.get(cv2.CAP_PROP_FRAME_COUNT)
        handshakeFrame = int(handshakeBufferTime/frameGapTime)+1
        requestSkipFrame = fps/requestFrameFps-handshakeFrame
        autoSpeedChangeFrame = 0
    except Exception as e:
        print(e)
        print(ws.id[:7],'time:',datetime.datetime.now(),",connect init fail")
        camera.release()
        ws.close()
        return

    client = plasma.connect(plasmaPath, "", 0)
    while True:
        msg = ws.receive()
        if ws.connected == False:
            print(ws.id[:7],'time:',datetime.datetime.now(),'avg fps',str(frameCount/((millis()-frameCountStartTime)/1000)))
            camera.release()
            print(ws.id[:7],'time:',datetime.datetime.now(),'close the websocket')
            ws.close()
            break
        if msg is not None:
            
            if not camera.isOpened():
                print('Could not start camera:')
                raise RuntimeError('Could not start camera.')
            else:
                fps = camera.get(cv2.CAP_PROP_FPS)
                frameGapTime = 1.0/fps * 1000
                # handshakeFrame = int(handshakeBufferTime/frameGapTime)+1
                requestSkipFrame = fps/requestFrameFps

                # speed changed
                if (q.qsize() > workerNume*15 ):
                    autoSpeedChangeFrame+=3
                elif q.qsize() > workerNume*12 and q.qsize() <=workerNume*15:
                    autoSpeedChangeFrame+=2
                elif q.qsize() > workerNume*10 and q.qsize() <=workerNume*12:
                    autoSpeedChangeFrame+=1
                elif q.qsize() <= workerNume*10:
                    autoSpeedChangeFrame-=2
                    if autoSpeedChangeFrame < 0:
                        autoSpeedChangeFrame = 0
                
                if autoSpeedChangeFrame > fps/requestFrameFps*2:
                    autoSpeedChangeFrame = fps/requestFrameFps*2
                    

                requestSkipFrame = fps/requestFrameFps+autoSpeedChangeFrame
                

                current = camera.get(cv2.CAP_PROP_POS_MSEC)
                current_frame = camera.get(cv2.CAP_PROP_POS_FRAMES)

                print(ws.id[:7],'time:',datetime.datetime.now(),",q size:",q.qsize()
                ,",current fps:"+str(fps/requestSkipFrame),',pos',current_frame,"rece siez:",ws.recv_queue.qsize(),",msg:",msg)
                if (total_frame != 0 and current_frame> total_frame):
                    print(ws.id[:7],'time:',datetime.datetime.now(),'finish the task,current_frame',current_frame,)
                    ws.close()
                if (frameCount%fps==0):
                    requestSkipFrame = requestSkipFrame - 1
                skipFrams = ((millis()-startTime)-current)/frameGapTime
                if (skipFrams < 1):
                    gevent.sleep(frameGapTime/1000)
                    # print(ws.id[:7],'time:',datetime.datetime.now(),'skipFrams < 1')
                    continue

                elif(skipFrams < rtspFrameBuffer and skipFrams > 1):
                    skipedFrame = 0
                    while (skipFrams < requestSkipFrame):
                        skipedFrame +=1
                        ret = camera.grab()
                        # print(ws.id[:7],'time:',datetime.datetime.now(),'skipFrams < ',requestSkipFrame)
                        gevent.sleep(frameGapTime/1000)
                        skipFrams = ((millis()-startTime)-current)/frameGapTime
                    if (skipFrams > rtspFrameBuffer):
                        print(ws.id[:7],'time:',datetime.datetime.now(),'skipedFrame > rtspFrameBuffer:',skipFrams ,",rtspFrameBuffer:",rtspFrameBuffer)
                        continue
                    count = skipedFrame
                    while(True):
                        count+=1
                        if count%requestSkipFrame==0:
                            ret ,img = camera.read()
                            retry = 0
                            while(ret == False and retry < 3):
                                gevent.sleep(5000)
                                ret ,img = camera.read()
                                print(ws.id[:7],'time:',datetime.datetime.now(),'camera put frame :',count,'retry times :',retry,",result:",ret)
                                retry +=1
                            if (ret == True) :
                                item = client.put(img)
                                plasma_id = item.binary()
                                buffer = cv2.imencode('.jpg', img)[1].tobytes()
                                frameCount+=1

                                print(ws.id[:7],'time:',datetime.datetime.now(),'camera put frame :',count,',plasma id:',plasma_id,', q size',q.qsize(),',ws:',ws.connected,",timestamp:",camera.get(cv2.CAP_PROP_POS_MSEC))

                                q.put(AnalyzeItem(buffer,plasma_id,ws,item,camera.get(cv2.CAP_PROP_POS_MSEC)))

                                gevent.sleep(0)
                                # print(ws.id[:7],'time:',datetime.datetime.now(),'sleep a muntout:',ret)
                                # gevent.sleep(handshakeBufferTime/2/1000)
                            else :
                                print(ws.id[:7],'time:',datetime.datetime.now(),'get frame camera fail,count:',count)
                                ws.close()
                                break
                        elif(count > skipFrams):
                            break
                        else:
                            ret = camera.grab()

def analyze(buffer,plasma_id,ws,timeStamp):
    timeout = gevent.Timeout(timeOutLimit)
    timeout.start()
    ret_address = base64.b64encode(plasma_id).decode('utf-8')
    tmp_id = millis()
    
    try:
        query = dict(parse_qsl(ws.environ['QUERY_STRING']))
        features = parse_qs(ws.environ['QUERY_STRING'])['feature']
        
        fields=[('image_type', 'jpg'),
                    ('tmp_id', str(tmp_id)),
                    ('plasma_id', ret_address),
                    ('conn_id',ws.id)]
        if ('faceset_token'in query):
            fields.append(('faceset_token',query["faceset_token"]))
        for feature in features:
            fields.append(('feature',feature))


        m = MultipartEncoder(
            fields=fields
            )
        print(ws.id[:7],'time:',datetime.datetime.now(),',analyze start,q size:',q.qsize(),',tmp id:',tmp_id,'pid:',plasma_id)
        req = grequests.post(analyzeAddress,data=m, headers={'Content-Type': m.content_type},timeout=timeOutLimit)
        res = req.send()
        print(ws.id[:7],'time:',datetime.datetime.now(),',analyze post finish,',res.response,",q.qsize:",q.qsize(),'tmp id:',tmp_id,',pid:',plasma_id)
        if res.response.status_code != 200:
            return
        analyze_data = json.loads(res.response.text)
        isWonderful = checkIsWonderful(analyze_data)
        if(query['always_return_image'] == '1'):
            jpg_as_text = base64.b64encode(buffer)
            base64_string = jpg_as_text.decode('utf-8')
            data = {'image_base64':base64_string,'time_stamp':timeStamp,'is_wonderful':isWonderful,'user_data':query['user_data'],'analyze_result':analyze_data}
        else:
            if isWonderful == 0:
                data = {'image_base64':'','time_stamp':timeStamp,'is_wonderful':isWonderful,'user_data':query['user_data'],'analyze_result':analyze_data}
            else:
                jpg_as_text = base64.b64encode(buffer)
                base64_string = jpg_as_text.decode('utf-8')
                data = {'image_base64':base64_string,'time_stamp':timeStamp,'is_wonderful':isWonderful,'user_data':query['user_data'],'analyze_result':analyze_data}

        
        jsonString = json.dumps(data)
        ws.send(jsonString)
    except Timeout as t:
        print(ws.id[:7],'time:',datetime.datetime.now(),'time out:',t,',tmp id:',tmp_id)
    except Exception as e:
        traceback.print_exc()
        print('analyze:',e)
    finally:
        timeout.close()

def checkIsWonderful(analyze_data):
    faces = analyze_data['faces']
    total = len(faces)
    happyCount = 0
    if (total == 0):
        return 0
    
    for i in range(total):
        primaryEmotion = faces[i]['emotion']['primary']
        if primaryEmotion == 'happy':
            happyCount+=1
    if (total>15 and happyCount/total > 0.5):
        return 1
    else:
        return 0


if __name__ == '__main__':
    app.run(debug=True, gevent=100)