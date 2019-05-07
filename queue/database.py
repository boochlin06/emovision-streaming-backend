from flask import Flask
from flask_sqlalchemy import SQLAlchemy
app = Flask(__name__)
app.config['SECRET_KEY'] = 'wansam'

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////db/video.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
class Video(db.Model):
    __tablename__ = 'videos'
    id = db.Column(db.Integer, primary_key=True)
    startTime = db.Column(db.String(120))
    endTime = db.Column(db.String(120))
    taskId = db.Column(db.Integer, unique=True)
    inputVideo = db.Column(db.String(120))
    outputVideo = db.Column(db.String(120), unique=True)
    outputJson = db.Column(db.String(120), unique=True)
    state = db.Column(db.String(10))
    size = db.Column(db.Integer)

    def __init__(self, endTime=None, startTime=None, taskId = None\
        ,inputVideo = None,outputVideo = None,size = None,state = "PROVISIONING"\
            ,outputJson=None ):
        self.endTime = endTime
        self.startTime = startTime
        self.taskId = taskId
        self.inputVideo = inputVideo
        self.outputVideo = outputVideo
        self.outputJson = outputJson
        self.size = size
        self.state = state
    def __repr__(self):
        return '<Video %r>' % (self.taskId)

    def to_json(self):
        json =  {
                'task_id': self.taskId,
                'start_time': self.startTime,
                'end_time': self.endTime,
                'input_video': self.inputVideo,
                'output_video' : self.outputVideo,
                'output_json' : self.outputJson,
                'size': self.size,
                'state' : self.state

                }
        return json

class Webhook(db.Model):
    __tablename__ = 'webhooks'
    id = db.Column(db.Integer, primary_key=True)
    app_key = db.Column(db.String(120))
    webhook = db.Column(db.String(120))

    def __init__(self, app_key=None, webhook=None):
        self.app_key = app_key
        self.webhook = webhook
        
    def __repr__(self):
        return '<Webhook %r>' % (self.webhook)

    def to_json(self):
        json =  {
                'app_key': self.app_key,
                'webhook': self.webhook,
                }
        return json

