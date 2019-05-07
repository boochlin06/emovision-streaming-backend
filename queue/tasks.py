import os
import time
from celery import Celery
from database import db
from database import Video
from database import Webhook
from flask import Flask
import base64
import cv2
import emotidraw
import requests
import json
import datetime
import traceback
import sys
import logging
try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse
import cv2

import pyarrow.plasma as plasma
import configparser
from requests_toolbelt import MultipartEncoder
from flask_uploads import UploadSet, configure_uploads, ALL
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379'),
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379')

tasks = Flask(__name__)
tasks.config['SECRET_KEY'] = 'wansam'
tasks.config['UPLOADED_VIDEOS_DEST'] =  os.getcwd()
celery = Celery('tasks', broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)
celery.config_from_object(__name__)
videos = UploadSet('videos',ALL)
configure_uploads(tasks, videos)

TEST_API_KEY = 'sheshin'
tasks.logger.addHandler(logging.StreamHandler(sys.stdout))
tasks.logger.setLevel(logging.DEBUG)
tasks.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////db/video.db'
tasks.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(tasks)
lengthInSecond = 1

config = configparser.ConfigParser()
config.read(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'config', 'analyze.ini'))
analyzeAddress=config.get('DEFAULT','analyzeAddress')
plasmaPath = config.get('DEFAULT','plasmaPath')


@celery.task(name='tasks.analyze.file',bind= True)
def analyze_file(self,inputfilename,output_json):
    # filename = videos.save(requestFile)
    inputPath = "/files/"+inputfilename
    statinfo = os.stat(inputPath)

    print("task: file size:",statinfo, ",path:",inputfilename, ",id:",self.request.id)
    # time.sleep(3)
    video = Video.query.filter_by(taskId=self.request.id).first()
    video.state = "PROCESSING"
    db.session.commit()
    try:
        file_name, file_extension = os.path.splitext(inputfilename)
        
        exists = Video.query.filter_by(outputVideo=file_name+ "-out.mp4")
        if (exists != None):
            file_name = file_name+"_"+str(self.request.id)
        outputName = process(inputPath,file_name,output_json==1)
        os.remove(inputPath)

        video.state= "FINISH"
        video.outputVideo = outputName + "-out.mp4"
        if (output_json==1):
            video.outputJson = outputName + "-out.json"
        video.endTime = millis()
        db.session.commit()
        post_webhook(video)
    except:
        video.state= "ERROR"
        db.session.commit()
        print(traceback.format_exc())
        tasks.logger.error(traceback.format_exc())
    
    return video.to_json()


@celery.task(name='tasks.analyze.url',bind= True)
def analyze_url(self,video_url,output_json):
    # filename = videos.save(requestFile)
    inputPath = video_url

    print("task:path:",video_url, ",id:",self.request.id)
    # time.sleep(3)
    video = Video.query.filter_by(taskId=self.request.id).first()
    video.state = "PROCESSING"
    db.session.commit()
    try:
        path = urlparse.urlsplit(video_url).path
        dirname, basename = os.path.split(path)
        file_name, file_extension = os.path.splitext(basename)
        exists = Video.query.filter_by(outputVideo=file_name+ "-out.mp4")
        if (exists != None):
            file_name = file_name+"_"+str(self.request.id)
        outputName = process(video_url,file_name,output_json==1)
        video.state= "FINISH"
        video.outputVideo = outputName + "-out.mp4"
        if (output_json==1):
            video.outputJson = outputName + "-out.json"
        video.endTime = millis()
        db.session.commit()
        post_webhook(video)
    except:
        video.state= "ERROR"
        db.session.commit()
        print(traceback.format_exc())
        tasks.logger.error(traceback.format_exc())
    
    return video.to_json()

def post_webhook(video):
    webhook = Webhook.query.filter_by(app_key=TEST_API_KEY).first()
    headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
    if (webhook != None):
        r = requests.post(webhook.webhook, data=json.dumps(video.to_json()), headers=headers)
        print("post webhook:",webhook.webhook, ",r:",r)
    


def process(source,file_name, enable_output_json):
    outputName = "/files/"+file_name + "-out.mp4"
    outputJsonName = "/files/"+file_name + "-out.json"
    if (enable_output_json):
        json_file = open(outputJsonName, "w+")
        json_file.write("[")

    url = analyzeAddress

    cap = cv2.VideoCapture(source)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    count = 0
    start_time = datetime.datetime.now()

    fourcc = cv2.VideoWriter_fourcc('m','p','4','v')
    videoWriter = cv2.VideoWriter(outputName,int(fourcc), fps,(int(width),int(height)),True)
    client = plasma.connect("/dev/shm/plasma", "", 0)

    while(True):
        count += 1
        ret, img = cap.read()
        if(not ret):
            break
        
        # _, img_encoded = cv2.imencode('.jpg', img)

        while True:
            try:
                item = client.put(img)
                plasma_id = item.binary()
                ret_address = base64.b64encode(plasma_id).decode('utf-8')
                tmp_id = millis()
                m = MultipartEncoder(
                    fields={'image_type': 'jpg',
                            'tmp_id': str(tmp_id),
                            'plasma_id': ret_address}
                )
                r = requests.post(url, data=m, headers={'Content-Type': m.content_type})
                data = r.json()

                if (enable_output_json):
                    if(count!= 1):
                        json_file.write(",")
                    json_file.write(json.dumps(data))
                    
                    json_file.flush()

                for face in data["faces"]:
                    rect = face["face_rectangle"]
                    emotidraw.draw_face_rect(img,rect["left"],rect["top"],rect["width"],rect["height"],face["emotion"]["primary"])
                    emotidraw.draw_face_emoji(img,rect["left"],rect["top"],rect["width"],rect["height"],face["emotion"]["primary"])

                videoWriter.write(img)
                duration = datetime.datetime.now()- start_time
                print("%d / %d  frame took %s. remain %s" % (count, total_frames, duration,(total_frames-count)*duration/count ), end="\r")
            except Exception as e: 
                tasks.logger.error(str(e))
                print(traceback.format_exc())
                tasks.logger.error(traceback.format_exc())
                break
                # continue
            break


    videoWriter.release()
    cap.release()

    if (enable_output_json):
        json_file.write("]")
        json_file.close()
    logging.debug("")
    # remove orignal video
    return file_name

def millis():
    return int(round(time.time() * 1000))