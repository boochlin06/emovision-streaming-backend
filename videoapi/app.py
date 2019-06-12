from flask import Flask
from flask import url_for,request,Response,send_file, send_from_directory,make_response,session,jsonify,redirect,render_template
from workers import celery
import celery.states as states
from celery.task.control import revoke
from urllib.parse import quote
import sys
import os
import time
import re
import mimetypes
from flask_uploads import UploadSet, configure_uploads, ALL
from requests_toolbelt import MultipartEncoder
import requests
import redis
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from database import db
from database import Video
from database import Webhook
import urllib3
import traceback
import json

from sqlalchemy.sql import func
import logging
try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse
import cv2

MB = 1 << 20
BUFF_SIZE = 10 * MB
SPACE_LIMIT = 20 * 1000 * MB
TEST_API_KEY = 'sheshin'

app = Flask(__name__)

app.config['SECRET_KEY'] = 'wansam'
app.config['UPLOADED_VIDEOS_DEST'] =  os.getcwd()+"/files/"
app.config['SESSION_TYPE'] = 'redis'  
app.config['SESSION_PERMANENT'] = False  
app.config['SESSION_USE_SIGNER'] = False  
app.config['SESSION_KEY_PREFIX'] = 'session:'
app.config['SESSION_REDIS'] = redis.Redis(host='redis', port=6379)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////db/video.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
db.create_all()
Session(app)

videos = UploadSet('videos',ALL)
configure_uploads(app, videos)

if __name__ != '__main__':
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)


@app.route('/v1/video',methods=['POST'])
def add():
    # video_file, video_url
    response = {}
    try:
        if request.method == 'POST' and 'video_url' in request.form:
            enableOutputJson = 1
            if ('output_json' in request.form): 
                enableOutputJson = request.form.get('output_json')
            video_url = request.form.get('video_url')
            app.logger.info(video_url)
            # video_data = urlparse(video_url)
            if (video_url.endswith(".mp4")):
                response_head = requests.head(video_url)
                length = int(response_head.headers.get('content-length'))
                if (length > 1 and validTotalVideosSize(length)== False):
                    response["success"] = False
                    response["error"] = {"code":2,"message":"Over Space Limit"}
                    return json.dumps(response) , 501
                else:
                    task = celery.send_task('tasks.analyze.url', args=[video_url,enableOutputJson], kwargs={})
                    video = Video(startTime=millis(),taskId=task.id,inputVideo=video_url,size=length)
                    db.session.add(video)
                    db.session.commit()
                    response["success"] = True
                    response["task"] = video.to_json()
                    return json.dumps(response),200
            else:
                response["success"] = False
                response["error"] = {"code":1,"message":"Invalid Argument:NOT MP4"}
                return json.dumps(response),400
        elif request.method == 'POST' and 'video_file' in request.files:
            enableOutputJson = 1
            if ('output_json' in request.form): 
                enableOutputJson = request.form.get('output_json')
            filename = videos.save(request.files['video_file'])
            _, file_extension = os.path.splitext(filename)
            inputPath = app.config['UPLOADED_VIDEOS_DEST']+filename
            size = os.stat(inputPath).st_size
            if (file_extension != ".mp4"):
                response["success"] = False
                response["error"] = {"code":1,"message":"Invalid Argument:NOT MP4"}
                return json.dumps(response),400
            if (validTotalVideosSize(size) == False):
                response["success"] = False
                response["error"] = {"code":2,"message":"Over Space Limit"}
                return json.dumps(response) , 501

            # app.logger.debug(filename)
            task = celery.send_task('tasks.analyze.file', args=[filename,enableOutputJson], kwargs={})
            video = Video(startTime=millis(),taskId=task.id,inputVideo=filename,size=size)
            db.session.add(video)
            db.session.commit()
            response["success"] = True
            response["task"] = video.to_json()
            return json.dumps(response),200
        else:
            response["success"] = False
            response["error"] = {"code":1,"message":"Invalid Argument:NO FORM DATA:video"}
            return json.dumps(response),400
    except :
        app.logger.error(traceback.format_exc())
        response["success"] = False
        response["error"] = {"code":0,"message":"UNKNOW"}
        return json.dumps(response),500
        
    

def validTotalVideosSize(newVideoSize):
    app.logger.info("new video size d :"+str(newVideoSize))
    totalSize = Video.query.with_entities(func.sum(Video.size)).all()
    if totalSize[0][0] is not None:
        if (newVideoSize + int(totalSize[0][0]) > SPACE_LIMIT):
            return False
        app.logger.info("total videos size:"+str(totalSize[0][0]))
        return True
    else:
        return True
    return True

@app.route('/v1/video/<string:task_id>',methods=['DELETE'])
def delete_task(task_id):
    response = {}
    try:
        video = Video.query.filter_by(taskId=task_id).first()
        if video is None:
            response["success"] = False
            response["error"] = {"code":1,"message":"Invalid Argument"}
            return json.dumps(response),400
        revoke(task_id,terminate=True)
        if (video.inputVideo is not None):
            filePath = app.config['UPLOADED_VIDEOS_DEST']+video.inputVideo
            if os.path.exists(filePath):
                os.remove(filePath)
            else:
                app.logger.error(str(task_id)+":The input file does not exist")
        if (video.outputVideo is not None):
            filePath = app.config['UPLOADED_VIDEOS_DEST']+video.outputVideo
            if os.path.exists(filePath):
                os.remove(filePath)
            else:
                app.logger.error(str(task_id)+"The output video file does not exist!")
        if (video.outputJson is not None):
            filePath = app.config['UPLOADED_VIDEOS_DEST']+video.outputJson
            if os.path.exists(filePath):
                os.remove(filePath)
            else:
                app.logger.error(str(task_id)+"The output json does not exist!")
        db.session.delete(video)
        db.session.commit()
        response["success"] = True
        return json.dumps(response) ,200
    except SystemExit as se:
        app.logger.error(str(se))
        app.logger.error(traceback.format_exc())
        response["success"] = True
        # response["error"] = {"code":0,"message":"UNKNOW"}
        return json.dumps(response) ,200
    except Exception as e:
        app.logger.error(str(e))
        app.logger.error(traceback.format_exc())
        response["success"] = False
        # response["error"] = {"code":0,"message":"UNKNOW"}
        return json.dumps(response) ,500


@app.route('/v1/video/<string:task_id>',methods=['GET'])
def check_task(task_id: str) -> str:
    response = {}
    try:
        res = celery.AsyncResult(task_id)
        video = Video.query.filter_by(taskId=task_id).first()
        if video is None:
            response["success"] = False
            response["error"] = {"code":1,"message":"Invalid Argument"}
            return json.dumps(response),400
        response["success"] = True
        response["task"] = video.to_json()
        return json.dumps(response),200
    except Exception as e:
        app.logger.error(traceback.format_exc())
        app.logger.error(str(e))
        response["success"] = False
        response["error"] = {"code":0,"message":"UNKNOW"}
        return json.dumps(response),500


@app.route('/v1/videos',methods=['GET'])
def list_tasks():
    response = {}
    try:
        list_all = Video.query.all()
        temp = []
        for item in list_all:
            temp.append(item.to_json())
        # res = json.dumps(temp)
        # app.logger.debug(res)
        response["success"] = True
        response["task"] = temp
        return json.dumps(response),200
    except Exception as e:
        app.logger.error(traceback.format_exc())
        app.logger.error(str(e))
        response["success"] = False
        response["error"] = {"code":0,"message":"UNKNOW"}
        return json.dumps(response),500


@app.route('/v1/video/download/video/<string:task_id>',methods=['GET'])
def download_Video(task_id):
    response = {}
    try:
        path = app.config['UPLOADED_VIDEOS_DEST']
        video = Video.query.filter_by(taskId=task_id).first()
        if video is None:
            response["success"] = False
            response["error"] = {"code":1,"message":"Invalid Argument"}
            return json.dumps(response),400
        elif video.state != "FINISH":
            response["success"] = False
            response["error"] = {"code":2,"message":"Task Not Finish"}
            return json.dumps(response),400
        if (video.outputVideo is not None):
            filename = video.outputVideo
            app.logger.info('download:'+filename)
            response = make_response(send_from_directory(path, filename,as_attachment=True))
            response.headers["Content-Disposition"] = "attachment; filename={0}; filename*=utf-8''{0}".format(
                quote(filename))
            #start, end = get_range(request)
            return response
            # return render_template('ws-test.html',video="files/"+filename)
        response["success"] = False
        response["error"] = {"code":1,"message":"Invalid Argument"}
        return json.dumps(response),400
    except Exception as e:
        app.logger.error(traceback.format_exc())
        app.logger.error(str(e))
        response["success"] = False
        response["error"] = {"code":0,"message":"UNKNOW"}
        return json.dumps(response),500

@app.route('/v1/video/download/json/<string:task_id>',methods=['GET'])
def download_Json(task_id):
    response = {}
    try:
        path = app.config['UPLOADED_VIDEOS_DEST']
        video = Video.query.filter_by(taskId=task_id).first()
        if video is None:
            response["success"] = False
            response["error"] = {"code":1,"message":"Invalid Argument"}
            return json.dumps(response),400
        elif video.state != "FINISH":
            response["success"] = False
            response["error"] = {"code":2,"message":"Task Not Finish"}
            return json.dumps(response),400
        if (video.outputJson is not None):
            filename = video.outputJson
            app.logger.info(str(task_id)+',download:'+filename)
            response = make_response(send_from_directory(path, filename))
            response.headers["Content-Disposition"] = "attachment; filename={0}; filename*=utf-8''{0}".format(
                quote(filename))
            return response,200
        response["success"] = False
        response["error"] = {"code":1,"message":"Invalid Argument"}
        return json.dumps(response),400
    except Exception as e:
        app.logger.error(traceback.format_exc())
        app.logger.error(str(task_id)+str(e))
        response["success"] = False
        response["error"] = {"code":0,"message":"UNKNOW"}
        return json.dumps(response),500

@app.route('/v1/video/webhook/',methods=['POST'])
def set_webhook():
    response = {}
    if 'webhook' in request.form:
        webhook = Webhook.query.filter_by(app_key=TEST_API_KEY).first()
        if (webhook is None):
            new_webhook = Webhook(app_key=TEST_API_KEY,webhook=request.form.get('webhook'))
            db.session.add(new_webhook)
            db.session.commit()
        else:
            webhook.webhook = request.form.get('webhook')
            db.session.commit()
        response["success"] = True
        return json.dumps(response),200
    else:
        response["success"] = False
        response["error"] = {"code":1,"message":"Invalid Argument:NO FORM DATA:webhook"}
        return json.dumps(response),400
    
@app.route('/v1/video/webhook/test',methods=['POST'])
def webhook_test_rece():
    if request.method == 'POST':
        # app.logger.debug(request.body)
        app.logger.debug(request.json)

def millis():
    return int(round(time.time() * 1000))