#!/usr/bin/env python
import base64
import datetime
import json
from importlib import import_module
from urllib.parse import parse_qsl

import cv2
import requests
from flask import Flask, Response, redirect, render_template, session, url_for
from flask_uwsgi_websocket import GeventWebSocket
from flask_wtf import FlaskForm
from gevent.queue import Queue
from requests_toolbelt import MultipartEncoder
import gevent
import traceback
import time


# import camera driver
from camera_opencv import Camera

app = Flask(__name__)
app.config['SECRET_KEY'] = 'hard to guess string'
websocket = GeventWebSocket(app)

def millis():
    return int(round(time.time() * 1000))

@app.route('/ws/bunny')
def index():
    return render_template('ws-test-local-bunny.html')

@app.route('/ws')
def index_ws():
    return render_template('ws-test.html')

@app.route('/ws/local')
def index_ws_local():
    return render_template('ws-test-local.html')

@websocket.route('/streaming/video')
def streaming(ws):
    r = parse_qsl(ws.environ['QUERY_STRING'])
    print(ws.environ['QUERY_STRING'])
    print('rtsp path:',r[2][1],'id:',r[0][1])
    retry = False
    camera = cv2.VideoCapture(r[2][1])
    fps = camera.get(cv2.CAP_PROP_FPS)
    timestamp = camera.get(cv2.CAP_PROP_POS_MSEC)
    startTime = millis()
    frameUsedTime = startTime
    frameGapTime = 1.0/fps * 1000
    frameCount = 0;
    print('fps:',fps,',timestamp:',timestamp,',start:',startTime,',fgt:',frameGapTime)

    while True:
        # print(datetime.datetime.now(),',receive size:',ws.recv_queue.qsize(),',retry:',retry)
        msg = ws.receive()
        # print(datetime.datetime.now(),',receive size:',ws.recv_queue.qsize(),',retry:',retry,msg)
        # print('streaming msg:',r[0][1])
        if msg is not None:
            if (msg.decode('utf-8')=='ack' or retry == True):
                frameCount+=1
                # print('decode,',datetime.datetime.now())
                # buffer = opencv_camera.get_frame()
                if not camera.isOpened():
                    img = Camera.imgs[0]
                    print('Could not start camera:')
                    raise RuntimeError('Could not start camera.')
                else:
                    # print('camera frames:',r[2][1])
                    # read current frame
                    current = camera.get(cv2.CAP_PROP_POS_MSEC)
                    skipFrams = ((millis()-startTime)-current)/frameGapTime
                    print(datetime.datetime.now(),'frame cost:',millis()-frameUsedTime,",total used time :"
                     ,millis()-startTime,",rtsp pos:",current,",skip:",skipFrams)    
                    frameUsedTime = millis()
                    count = 0
                    while True:
                        if (count<skipFrams):
                            ret = camera.grab()
                        # ret ,img = camera.read()
                        elif (count>=skipFrams):
                            ret ,img = camera.read()
                            break
                        if (ret == False):
                            print('read falure')
                            # time.sleep(0.5)
                            retry = True
                            break
                        count+=1
                if retry== True:
                    camera.release()
                    # cv2.destroyAllWindows()
                    startTime = millis()
                    camera = cv2.VideoCapture(r[2][1])
                    ret ,img = camera.read()
                    # continue

                # # encode as a jpeg image and return it
                try:
                    buffer = cv2.imencode('.jpg', img)[1].tobytes()
                    # print('decode,',datetime.datetime.now())
                    # analyzeQueue.put(AnalyzeRequest(buffer,r[0][1],ws))
                    analyze(buffer,r[0][1],ws)
                    retry = False
                except Exception as e:
                    print(e)
                    break
        else:
            camera.release()
            cv2.destroyAllWindows()
            print('close the websocke:',Camera.video_source)
            print('avg fps',(millis()-startTime)/frameCount)
            return

def analyze(buffer,id,ws):
    # print(datetime.datetime.now(),',analyze,')
    m = MultipartEncoder(
            fields={'image_type': 'jpg',
                    'image_binary':('upload_image.jpg',buffer,'text/plain')}
            )
    res = requests.post('http://192.168.3.11:8001/emotibot/analyze',data=m, headers={'Content-Type': m.content_type})
    # print(datetime.datetime.now(),',analyze post finish,',res)
    jpg_as_text = base64.b64encode(buffer)
    base64_string = jpg_as_text.decode('utf-8')
    analyze_data = json.loads(res.text)
    data = {'image_base64':base64_string,'id':id,'analyze_result:':analyze_data}
    jsonString = json.dumps(data)
    ws.send(jsonString)
    print(datetime.datetime.now(),'analyze finish, server time used:',analyze_data['time_used'])

if __name__ == '__main__':
    app.run(debug=True, gevent=100)
