import tornado.ioloop 
import tornado.web 
import tornado.httpclient 
from tornado.gen import multi
import tornado.gen as gen
from tornado import escape
import os
import cv2
import pyarrow.plasma as plasma
import base64
import io
import numpy as np
import json
import traceback
import infer_body as bodyservice
import time
import pyarrow
import uuid
import redis
import math
import logging
import random
import emotidraw
import datetime
import functools

emotionColorMap =  {}
emotionColorMap["angry"] = (57,65,243)
emotionColorMap["confused"] = (0,154,154)
emotionColorMap["contempt"] = (168,133,4)
emotionColorMap["disgust"] = (166,132,5)
emotionColorMap["fear"] = (35,61,111)
emotionColorMap["happy"] = (87,210,243)
emotionColorMap["neutral"] = (252,255,252)
emotionColorMap["sad"] = (160,192,12)
emotionColorMap["surprise"] = (117,49,206)

logging.basicConfig(level=logging.INFO,format='%(asctime)s %(lineno)d %(message)s')

r = redis.Redis(host='redis', port=6379)
# sub = r.pubsub()
# sub.subscribe('behavior_threshold_channel')
# for message in sub.listen():
#     print('Got message', message)
#     if (
#         isinstance(message.get('data'), bytes) and
#         message['data'].decode() == 'GREETING'
#     ):
#         print('Hello')

PIPELINE_URL = os.environ['PIPELINE_URL'] 

# PIPELINE_URL = "http://192.168.0.108:8001"

bodyservice.initBodyServiceClient()

client = plasma.connect(os.environ['PLASMA_PATH'], "", 0)

wonderful_face_count_threshold = 8
wonderful_hands_up_pct = 0.2
wonderful_emotion_pct = 0.6

threshold_set = {
    "mouth_open_threshold",
    "face_height_threshold_for_mouth_status",
    # "eye_eyebrow_dist_ratio_threshold",
    "eyes_open_threshold_l",
    "eyes_open_threshold_m",
    "eyes_open_threshold_s",
    "large_face_height_lower_bound_for_eyes_status",
    "middle_face_height_lower_bound_for_eyes_status"
}
threshold = {
    "mouth_open_threshold":5,
    "face_height_threshold_for_mouth_status":128,
    # "eye_eyebrow_dist_ratio_threshold":0.1,
    "eyes_open_threshold_l":4.7,
    "eyes_open_threshold_m":4.5, 
    "eyes_open_threshold_s":3.5,
    "large_face_height_lower_bound_for_eyes_status":110,
    "middle_face_height_lower_bound_for_eyes_status":85
}




eyes_open_threshold = 0.5

headpose_all_pass_pct_threshold = 0.85
headpose_side_pass_pct_threshold = 0.85
headpose_all_pass_yaw_threshold = 20 

headpose_side_pass_yaw_for_center_threshold = 10
headpose_side_width_threshold = 0.3

headpose_side_pass_pitch_threshold = 20
headpose_bottom_height_threshold = 0.55

headpose_pct_rule = [100,88.8,77.7,66.6,55.5,44.4,33.3,22.2,11.1,11,1]
headpose_special_rule = [100,100,87.5,75,62.5,50,37.5,25,12.5,12.5]

eyes_score_punishment = 0.5
mouth_score_bonus = 0.3

emotion__rule = {
    'happy':100,
    'neutral':88,
    'confused':74,
    'surprise':74,
    'angry':60,
    'fear':60,
    'disgust':60,
    'contempt':60,
    'sad':60
}

concentration_weight = {
    'head_yaw': 0.22,
    'head_pitch':0.22,
    'emotion':0.38,
    'eyes':0.18
}

vitality_weight = {
    'emotion': 0.35,
    'mouth':0.33,
    'eyes':0.19,
    'hands':0.13
}

redis_expire_time = 300

save_np = False

def toScore(score):
    if score > 100:
        return 100
    elif score < 0:
        return 0
    else:
        return score

def count_to_eyes_score(count):
    score = 100 - eyes_score_punishment * count
    return toScore(score)

def count_to_mouth_score(count):
    score =  mouth_score_bonus * count
    return toScore(score)

def get_img_from_fileinfo(fileinfo):
    body = fileinfo["body"]
    decoded = cv2.imdecode(np.frombuffer(body, np.uint8), -1)
    return decoded

def get_plasma_id_from_img(img):
    item = client.put(img)
    return base64.b64encode(item.binary()).decode('utf-8')

def landmark_dist(p1,p2):
    # return math.hypot(p2["x"] - p1["x"], p2["y"] - p1["y"])
    return abs(p2["y"] - p1["y"])


mouth_dist = np.array([])
mouth_dist_pct = np.array([])
eyes_dist = np.array([])
eyes_dist_pct = np.array([])
keypoints = np.array([])
save_counter = 0

def get_mouth_distance(face):
    global mouth_dist
    global mouth_dist_pct
    landmark = face["landmark"]
    scaler = 100/face['face_rectangle']['height'] 
    facial_landmark = landmark["facial_landmark"]
    headpose = landmark["facial_head_pose"]
    if abs(headpose["pitch"]) > 30 or abs(headpose["yaw"]) > 30 or abs(headpose["roll"]) > 20:
        return None, None

    dist = landmark_dist(facial_landmark["62"],facial_landmark["66"])
    mouth_dist = np.append(mouth_dist, dist)
    mouth_dist_pct = np.append(mouth_dist_pct,dist*scaler)

def get_eyes_distance(face):
    global eyes_dist
    global eyes_dist_pct
    landmark = face["landmark"]
    scaler = 100/face['face_rectangle']['height'] 
    facial_landmark = landmark["facial_landmark"]
    headpose = landmark["facial_head_pose"]
    if abs(headpose["pitch"]) > 30 or abs(headpose["yaw"]) > 30 or abs(headpose["roll"]) > 20:
        return None, None

    dist = min( [landmark_dist(facial_landmark["38"],facial_landmark["40"]) , landmark_dist(facial_landmark["43"],facial_landmark["47"])] )
    eyes_dist = np.append(eyes_dist,dist)
    eyes_dist_pct = np.append(eyes_dist_pct,dist*scaler)

    

def get_mouth_status(landmark):
    facial_landmark = landmark["facial_landmark"]
    headpose = landmark["facial_head_pose"]
    if abs(headpose["pitch"]) > 30 or abs(headpose["yaw"]) > 30 or abs(headpose["roll"]) > 20:
        return 2
    if landmark_dist(facial_landmark["62"],facial_landmark["66"]) > mouth_open_threshold:
        return 1
    else:
        return 0

def get_eyes_status(landmark):
    facial_landmark = landmark["facial_landmark"]
    headpose = landmark["facial_head_pose"]
    if abs(headpose["pitch"]) > 30 or abs(headpose["yaw"]) > 30 or abs(headpose["roll"]) > 20:
        return 2
    if landmark_dist(facial_landmark["38"],facial_landmark["40"]) > eyes_open_threshold and landmark_dist(facial_landmark["43"],facial_landmark["47"]) > eyes_open_threshold:
        return 1
    else:
        return 0

def get_mouth_status_v2(face):
    global threshold_set
    global threshold

    landmark = face["landmark"]
    facial_landmark = landmark["facial_landmark"]
    headpose = landmark["facial_head_pose"]
    
    if abs(headpose["pitch"]) > 30 or abs(headpose["yaw"]) > 30 or abs(headpose["roll"]) > 20:
        return 2

    dist = landmark_dist(facial_landmark["62"],facial_landmark["66"])
    
    if face['face_rectangle']['height'] >= threshold["face_height_threshold_for_mouth_status"] and dist >= threshold["mouth_open_threshold"]:
        return 1
    elif dist >= face['face_rectangle']['height']/threshold["face_height_threshold_for_mouth_status"] * threshold["mouth_open_threshold"]:
        return 1
    else:
        return 0

    

def get_eyes_status_v2(face):
    global threshold_set
    global threshold
    
    landmark = face["landmark"]
    height = face['face_rectangle']['height']
    # print(height)
    facial_landmark = landmark["facial_landmark"]
    headpose = landmark["facial_head_pose"]
    
    if abs(headpose["pitch"]) > 30 or abs(headpose["yaw"]) > 30 or abs(headpose["roll"]) > 20:
        return 2

    dist_r_eb_eye = landmark_dist(facial_landmark["39"],facial_landmark["21"])
    dist_l_eb_eye = landmark_dist(facial_landmark["42"],facial_landmark["22"])

    r_eye_ratio = dist_r_eb_eye/height
    l_eye_ratio = dist_l_eb_eye/height

    if r_eye_ratio < 0.1 or l_eye_ratio  < 0.1:
        return 2

    dist_r_2 = landmark_dist(facial_landmark["37"],facial_landmark["41"])
    dist_r_1 = landmark_dist(facial_landmark["38"],facial_landmark["40"])
    dist_l_1 = landmark_dist(facial_landmark["43"],facial_landmark["47"])
    dist_l_2 = landmark_dist(facial_landmark["44"],facial_landmark["46"])
    
    eye_dist = (dist_l_1 + dist_l_2 + dist_r_1 + dist_r_2)/4.0

    

    if height >= threshold["large_face_height_lower_bound_for_eyes_status"]:
        if eye_dist >= threshold["eyes_open_threshold_l"]: 
            return 1
        else:
            return 0
    elif height < threshold["large_face_height_lower_bound_for_eyes_status"] and height >= threshold["middle_face_height_lower_bound_for_eyes_status"]:
        if eye_dist >= threshold["eyes_open_threshold_m"]:
            return 1
        else:
            return 0
    else:
        if eye_dist >= threshold["eyes_open_threshold_s"]: 
            return 1
        else:
            return 0

def is_side(width,height,face):
    face_center = face['face_rectangle']['left']+face['face_rectangle']['width']/2
    if face_center < width * headpose_side_width_threshold or face_center > width * (1-headpose_side_width_threshold):
        return True
    return False
    
def get_headpose_score_list_by_yaw(width,height,faces):
    score_list = [0] * len(faces)

    center_list = []
    side_list = []
    allpass_count = 0
    sidepass_count = 0

    for i, face in enumerate(faces):
        yaw = abs(face['landmark']['facial_head_pose']['yaw'])
        if is_side(width,height,face):
            side_list.append(i)
            if yaw > headpose_all_pass_yaw_threshold:
                allpass_count += 1
                sidepass_count += 1
        else:
            center_list.append(i)
            if yaw > headpose_all_pass_yaw_threshold:
                allpass_count += 1
            if yaw > headpose_side_pass_yaw_for_center_threshold:
                sidepass_count += 1
        
    if allpass_count > len(faces) * headpose_all_pass_pct_threshold:
        # logging.debug("all pass")
        score_list = [100] * len(faces)
    else:
        for i in center_list:
            # logging.debug("set center score")
            level = math.floor(abs(faces[i]['landmark']['facial_head_pose']['yaw'])/10)
            if level <= 9:
                score_list[i] = headpose_pct_rule[level]
            else:
                score_list[i] = 0
        if sidepass_count > len(faces) * headpose_side_pass_pct_threshold:
            # logging.debug("side pass")
            for i in side_list:
                score_list[i] = 100
        else:
            # logging.debug("set side score")
            for i in side_list:
                level = math.floor(abs(faces[i]['landmark']['facial_head_pose']['yaw'])/10)
                if level <= 9:
                    score_list[i] = headpose_special_rule[level]
                else:
                    score_list[i] = 0
    return score_list

def get_headpose_score_list_by_pitch(width,height,faces):
    score_list = [0] * len(faces)

    center_list = []
    side_list = []
    sidepass_count = 0

    level_list = [0]*10

    for i, face in enumerate(faces):
        if face['landmark']['facial_head_pose']['pitch'] < 0:
            face['landmark']['facial_head_pose']['pitch'] = 0
        pitch = abs(face['landmark']['facial_head_pose']['pitch'])
        level = math.floor(abs(faces[i]['landmark']['facial_head_pose']['pitch'])/10)
        if level <= 9:
            level_list[level] += 1
        if pitch < headpose_side_pass_pitch_threshold:
                sidepass_count += 1
        if is_side(width,height,face):
            side_list.append(i)
        else:
            center_list.append(i)
        
        
    if max(level_list) > len(faces) * headpose_all_pass_pct_threshold:
        for i in center_list:
            score_list[i] = 100
    else:
        for i in center_list:
            level = math.floor(abs(faces[i]['landmark']['facial_head_pose']['pitch'])/10)
            if level <= 9:
                score_list[i] = headpose_pct_rule[level]
            else:
                score_list[i] = 0
        if sidepass_count > len(faces) * headpose_side_pass_pct_threshold:
            # logging.debug("side pass")
            for i in side_list:
                score_list[i] = 100
        else:
            # logging.debug("set side score")
            for i in side_list:
                level = math.floor(abs(faces[i]['landmark']['facial_head_pose']['pitch'])/10)
                if level <= 9:
                    score_list[i] = headpose_special_rule[level]
                else:
                    score_list[i] = 0
    return score_list

def get_emotion_score_list(faces):
    return [emotion__rule[face['emotion']['primary']] for face in faces ]



def get_eyes_score_list(conn_id,faces):
    pipe = r.pipeline()
    for face in faces:
        key = conn_id+face['face_token'] + 'eyes'
        if face['behavior']['eyes_status'] == 0:
            pipe.incr(key)
        else:
            pipe.incrby(key,0)
        pipe.expire(key,redis_expire_time)

    score_list = pipe.execute()
    score_list = score_list[0::2]
    score_list = [count_to_eyes_score(x)for x in score_list ]
    return score_list


def get_mouth_score_list(conn_id,faces):
    pipe = r.pipeline()
    for face in faces:
        key = conn_id+face['face_token'] + 'mouth'
        if face['behavior']['mouth_status'] == 1:
            pipe.incr(key)
        else:
            pipe.incrby(key,0)
        pipe.expire(key,redis_expire_time)

    score_list = pipe.execute()
    score_list = score_list[0::2]
    score_list = [count_to_mouth_score(x)for x in score_list ]
    return score_list

def get_hands_up_score_list(conn_id,faces,hands_up_count):
    hands_up_bonus = hands_up_count/len(faces)
    pipe = r.pipeline()
    for face in faces:
        key = conn_id+face['face_token'] + 'hands'
        pipe.incrbyfloat(key,hands_up_bonus)
        pipe.expire(key,redis_expire_time)
    score_list = pipe.execute()
    score_list = score_list[0::2]
    score_list = [toScore(x)for x in score_list ]
    return score_list

def resp_callback(future, feature,handler,start):
    if feature == "FACE":
        handler.face_time = int((time.time()-start)*1000)
    if feature == "BODY":
        handler.body_time = int((time.time()-start)*1000)


    
class MainHandler(tornado.web.RequestHandler):

    def write_error(self, status_code, **kwargs):
        self.set_header('Content-Type', 'application/json')
        logging.debug(self._reason)
        print("ERROR: tmp_id, face, body = ",datetime.datetime.now(),self.tmp_id,self.face_time,self.body_time)
        # logging.debug('%s' % self.request.body)
        self.finish(json.dumps({
            'request_id': self.request_id,
            'error': status_code,
            'message': self._reason,
        }))

    async def post(self):
        # files = self.request.files['image_binary']
        # logging.debug('%s' % files)
        self.request_id = str(uuid.uuid4())
        self.tmp_id = None
        self.face_time = None
        self.body_time = None
        
        img = None
        img_bytes = None

        orgimg = None

        # logging.debug('%s %s' % ("self.request.body",self.request.body))
        conn_id = self.get_argument("conn_id","default_conn_id",True)
        tmp_id = self.get_argument("tmp_id","default_tmp_id",True)
        self.tmp_id = tmp_id

        

        skip_count = int(r.incr(conn_id))%3
        r.expire(conn_id,redis_expire_time)
        
        skip_body = True if skip_count != 0 else False

        width = None
        height = None
        # use plasma image
        if self.get_argument("plasma_id","",True) != "":
            # logging.debug("get plasma_id")
            plasma_id = self.get_argument("plasma_id","",True)
            # logging.debug('%s %s' % ("plasma_id",plasma.ObjectID(base64.b64decode(plasma_id))))
            # img = client.get(plasma.ObjectID(base64.b64decode(plasma_id)),timeout_ms=500)
            global client
            try:
                img = client.get(plasma.ObjectID(base64.b64decode(plasma_id)),timeout_ms=500)
                orgimg = client.get(plasma.ObjectID(base64.b64decode(plasma_id)),timeout_ms=500)
            except pyarrow.lib.ArrowIOError:
                try:
                    client = plasma.connect(os.environ['PLASMA_PATH'], "", 0)
                    img = client.get(plasma.ObjectID(base64.b64decode(plasma_id)),timeout_ms=500)
                except pyarrow.lib.ArrowIOError:
                    raise SystemExit
                    # sys.exit()
            # img = client.get(plasma.ObjectID(base64.b64decode(plasma_id)),timeout_ms=500)
            # img = cv2.resize(img, (640, 480))
            height, width, channels = img.shape

            img = cv2.resize(img, (1300, 800))
            _,  img_bytes = cv2.imencode('.jpg', img)
            img_bytes = img_bytes.tobytes()
        # use image_binary
        elif "image_binary" in self.request.files:
            fileinfo = self.request.files['image_binary'][0]
            img = get_img_from_fileinfo(fileinfo)
            img_bytes = fileinfo["body"]           
        else :
            raise tornado.web.HTTPError(status_code=400,reason="No Image Input")


        # logging.debug(height, width, channels)

        feature = self.get_arguments("feature",True)
        # if  "BODY" in feature:
        #     feature.remove('BODY')
        if skip_body and ('BODY' in feature):
            feature.remove('BODY')
        if self.get_argument("conn_id",None,True) == None:
            feature.append('FACE')



        feature_list = []
        request_list = []
        response_list = []
        start = time.time()
        
        if "FACE" in feature:
            feature_list.append("FACE")
            request_list.append(tornado.httpclient.AsyncHTTPClient().fetch(tornado.httpclient.HTTPRequest(PIPELINE_URL+"/emotibot/v2/analyze", 'POST', body=self.request.body, headers=self.request.headers )))
        if  "BODY" in feature:
            feature_list.append("BODY")
            request_list.append(bodyservice.do_infer(img_bytes))
        # response_list = await multi(request_list)   

        for i in range(len(feature_list)):
            if feature_list[i] == "FACE":
                request_list[i].add_done_callback(
                    functools.partial(resp_callback, feature="FACE", handler=self,start=start)
                )
            if feature_list[i] == "BODY":
                request_list[i].add_done_callback(
                    functools.partial(resp_callback, feature="BODY",handler=self,start=start)
                )

        for i in range(len(feature_list)):     
            resp = await request_list[i]
            response_list.append(resp)


            
        print("tmp_id, face, body = ",datetime.datetime.now(),self.tmp_id,self.face_time,self.body_time)

        summary = {}
        for i in reversed(range(len(feature_list))):
            if feature_list[i] == "FACE":
                summary = json.loads(response_list[i].body.decode('utf-8'))
            elif feature_list[i] == "BODY":
                summary['hands_up_count'] = bodyservice.parse_result(response_list[i])
                summary.setdefault('time_used',int((time.time()-start)*1000))
                # logging.info("hands_up_time_used %s %d",time.time()-start, summary['hands_up_count'])
                summary.setdefault('result_code',0)
                summary.setdefault('result_msg',"success")
                summary.setdefault('request_id',self.request_id)
        # logging.debug("done")


        

        summary['is_wonderful'] = 0

        plasma_id = self.get_argument("plasma_id","",True)

        if "FACE" in feature:
            # add mouth_status, eyes_status and remove landmark
            for i, face in enumerate(summary["faces"]):
                summary["faces"][i]["behavior"] = {
                    'mouth_status': get_mouth_status_v2(face),
                    'eyes_status': get_eyes_status_v2(face),
                }
                if save_np:
                    get_mouth_distance(face)
                    get_eyes_distance(face)
                
                summary["faces"][i]["landmark"].pop("facial_landmark")
            
            if self.get_argument("faceset_token",None,True) != None:
                # # asign random face token for test
                # fake_face_token_list = ["a","b","c","d","e","f","g","h","i"] 
                # for i in range(len(fake_face_token_list)):
                #     summary['faces'][i]['face_token'] = fake_face_token_list[i]
                
                not_recognized_face_list = [x for x in summary['faces'] if x['face_token'] == ""]
                # logging.debug(len(not_recognized_face_list))
                recognized_face_list = [x for x in summary['faces'] if x['face_token'] != ""]
                # logging.debug(len(recognized_face_list))


                if len(recognized_face_list) != 0:
                    start = time.time()
                    headpose_score_list_by_yaw = get_headpose_score_list_by_yaw(width,height,recognized_face_list)
                    logging.debug('%s %s' % ("headpose_score_list_by_yaw",headpose_score_list_by_yaw))
                    headpose_score_list_by_pitch = get_headpose_score_list_by_pitch(width,height,recognized_face_list)
                    logging.debug('%s %s' % ("headpose_score_list_by_pitch",headpose_score_list_by_pitch))
                    emotion_score_list = get_emotion_score_list(recognized_face_list)
                    logging.debug('%s %s' % ("emotion_score_list",emotion_score_list))
                    mouth_score_list = get_mouth_score_list(conn_id,recognized_face_list)
                    logging.debug('%s %s' % ("mouth_score_list",mouth_score_list))
                    eyes_score_list = get_eyes_score_list(conn_id,recognized_face_list)
                    logging.debug('%s %s' % ("eyes_score_list",eyes_score_list))
                    hands_up_score_list = get_hands_up_score_list(conn_id,recognized_face_list, 0 if 'hands_up_count' not in summary else summary['hands_up_count'])
                    logging.debug('%s %s' % ("hands_up_score_list",hands_up_score_list))
                    concentration_score_list =[ round((x[0]*concentration_weight['head_yaw']+ x[1]*concentration_weight['head_pitch']+x[2]*concentration_weight['emotion']+x[3]*concentration_weight['eyes'])/100,2) for x in  zip(headpose_score_list_by_yaw,headpose_score_list_by_pitch,emotion_score_list,eyes_score_list)]
                    logging.debug('%s %s' % ("concentration_score_list",concentration_score_list))
                    vitality_score_list =[ round((x[0]*vitality_weight['emotion']+ x[1]*vitality_weight['mouth']+x[2]*vitality_weight['eyes']+x[3]*vitality_weight['hands'])/100,2) for x in  zip(emotion_score_list,mouth_score_list,eyes_score_list,hands_up_score_list)]
                    logging.debug('%s %s' % ("vitality_score_list",vitality_score_list))
                    
                    for i in range(len(recognized_face_list)):
                        recognized_face_list[i]['behavior']['concentration'] = concentration_score_list[i]
                        recognized_face_list[i]['behavior']['vitality'] = vitality_score_list[i]
                    summary['faces'] = recognized_face_list + not_recognized_face_list
                    # logging.debug(time.time()-start)
                    
                # is wonderful
                if len(summary['faces']) >= wonderful_face_count_threshold:
                    if 'hands_up_count' in summary and summary['hands_up_count'] / len(summary['faces']) >= wonderful_hands_up_pct:
                        
                        summary['is_wonderful'] = 1
                        orgimg_fn = str(random.random())
                        logging.debug('====wonderful hands up=========%s' % orgimg_fn)
                        logging.debug('%d' % summary['hands_up_count'])
                        logging.debug('%d' % len( summary['faces'] ))
                        # cv2.imwrite('wonderful/'+orgimg_fn+'.png',orgimg)
                        # cv2.imwrite('wonderful/'+orgimg_fn+'.jpg',orgimg)
                    else:
                        positive_count = len([1 for x in summary['faces'] if x['emotion']['primary'] == 'happy' ])
                        if positive_count / len(summary['faces']) >= wonderful_emotion_pct:
                            summary['is_wonderful'] = 1
                            orgimg_fn = str(random.random())
                            logging.debug('====wonderful happy========= % s' % orgimg_fn)
                            logging.debug('%d' % len([1 for x in summary['faces'] if x['emotion']['primary'] == 'happy' ]))
                            logging.debug('%d' % len( summary['faces'] ))
                        
                            # cv2.imwrite('wonderful/'+orgimg_fn+'.png',orgimg)
                            # cv2.imwrite('wonderful/'+orgimg_fn+'.jpg',orgimg)

        summary.setdefault('time_used',0)
        summary.setdefault('result_code',0)
        summary.setdefault('result_msg',"success")
        summary.setdefault('request_id',self.request_id)
        if self.get_argument("conn_id",None,True) == None:
            del summary['is_wonderful']

 
        
        if save_np:
            # global save_counter
            # save_counter += 1
            # # if save_counter%600 ==0:
            # logging.debug("==save==",mouth_dist.shape)
            target =  'om'
            np.save('npy/'+target+'/mouth_dist',mouth_dist)
            np.save('npy/'+target+'/mouth_dist_pct',mouth_dist_pct)
            np.save('npy/'+target+'/eyes_dist',eyes_dist)
            np.save('npy/'+target+'/eyes_dist_pct',eyes_dist_pct)
            # np.save('npy/'+target+'/keypoints',keypoints)
        

        # logging.debug(mouth_dist,mouth_dist_pct,eyes_dist,eyes_dist_pct)
        self.write(summary)


class DrawHandler(tornado.web.RequestHandler):

    def write_error(self, status_code, **kwargs):
        self.set_header('Content-Type', 'application/json')
        logging.debug(self._reason)
        self.finish(json.dumps({
            'request_id': self.request_id,
            'error': status_code,
            'message': self._reason,
        }))

    async def post(self):
        self.request_id = str(uuid.uuid4())
        
        img = None
        img_bytes = None
        orgimg = None
        orgimg_fn = str(random.random())
        conn_id = self.get_argument("conn_id","default_conn_id",True)

        

        skip_count = int(r.incr(conn_id))%3
        r.expire(conn_id,redis_expire_time)
        
        skip_body = True if skip_count != 0 else False

        width = None
        height = None
        if self.get_argument("plasma_id","",True) != "":
            plasma_id = self.get_argument("plasma_id","",True)
            global client
            try:
                img = client.get(plasma.ObjectID(base64.b64decode(plasma_id)),timeout_ms=500)
                orgimg = client.get(plasma.ObjectID(base64.b64decode(plasma_id)),timeout_ms=500)
            except pyarrow.lib.ArrowIOError:
                try:
                    client = plasma.connect(os.environ['PLASMA_PATH'], "", 0)
                    img = client.get(plasma.ObjectID(base64.b64decode(plasma_id)),timeout_ms=500)
                except pyarrow.lib.ArrowIOError:
                    raise SystemExit
            height, width, channels = img.shape

            img = cv2.resize(img, (640, 480))
            _,  img_bytes = cv2.imencode('.jpg', img)
            img_bytes = img_bytes.tobytes()
        elif "image_binary" in self.request.files:
            fileinfo = self.request.files['image_binary'][0]
            orgimg_fn =  fileinfo['filename']
            img = get_img_from_fileinfo(fileinfo)
            orgimg = img
            # img_bytes = fileinfo["body"]   
            img = cv2.resize(img, (640, 480))
            _,  img_bytes = cv2.imencode('.jpg', img)
            img_bytes = img_bytes.tobytes()
            # print(img.shape)
            # print(orgimg.shape)

            # f = open('draw/src/'+orgimg_fn+'.jpg')    
            # file_body = self.request.files['filefieldname'][0]['body']
            # img = Image.open(StringIO.StringIO(file_body))
            # img.save("../img/", img.format)
                
        else :
            raise tornado.web.HTTPError(status_code=400,reason="No Image Input")



        feature = self.get_arguments("feature",True)
        # if skip_body and ('BODY' in feature):
        #     feature.remove('BODY')
        if self.get_argument("conn_id",None,True) == None:
            feature.append('FACE')

        feature_list = []
        request_list = []
        if "FACE" in feature:
            feature_list.append("FACE")
            request_list.append(tornado.httpclient.AsyncHTTPClient().fetch(tornado.httpclient.HTTPRequest(PIPELINE_URL+"/emotibot/v2/analyze", 'POST', body=self.request.body, headers=self.request.headers )))
        if  "BODY" in feature:
            feature_list.append("BODY")
            start = time.time()
            request_list.append(bodyservice.do_infer(img_bytes))
        response_list = await multi(request_list)   

        summary = {}
        for i in range(len(feature_list)):
            if feature_list[i] == "FACE":
                summary = json.loads(response_list[i].body.decode('utf-8'))
            elif feature_list[i] == "BODY":
                summary['hands_up_count'] = bodyservice.parse_result(response_list[i])
                summary.setdefault('time_used',int((time.time()-start)*1000))
                # logging.debug("hands_up_time_used",time.time()-start, summary['hands_up_count'])
                summary.setdefault('result_code',0)
                summary.setdefault('result_msg',"success")
                summary.setdefault('request_id',self.request_id)

        summary['is_wonderful'] = 0

        plasma_id = self.get_argument("plasma_id","",True)

        if "FACE" in feature:
            # add mouth_status, eyes_status and remove landmark
            for i, face in enumerate(summary["faces"]):
                summary["faces"][i]["behavior"] = {
                    'mouth_status': get_mouth_status_v2(face),
                    'eyes_status': get_eyes_status_v2(face),
                }
                # summary["faces"][i]["behavior"]['mouth_dist'], summary["faces"][i]["behavior"]['mouth_dist_pct'] = get_mouth_distance(face)
                # summary["faces"][i]["behavior"]['eyes_dist'], summary["faces"][i]["behavior"]['eyes_dist_pct'] = get_eyes_distance(face)
                get_mouth_distance(face)
                get_eyes_distance(face)
                
                # summary["faces"][i]["landmark"].pop("facial_landmark")
            
            if self.get_argument("faceset_token",None,True) != None:
                not_recognized_face_list = [x for x in summary['faces'] if x['face_token'] == ""]
                recognized_face_list = [x for x in summary['faces'] if x['face_token'] != ""]

                if len(recognized_face_list) != 0:
                    start = time.time()
                    headpose_score_list_by_yaw = get_headpose_score_list_by_yaw(width,height,recognized_face_list)
                    logging.debug('%s %s' % ("headpose_score_list_by_yaw",headpose_score_list_by_yaw))
                    headpose_score_list_by_pitch = get_headpose_score_list_by_pitch(width,height,recognized_face_list)
                    logging.debug('%s %s' % ("headpose_score_list_by_pitch",headpose_score_list_by_pitch))
                    emotion_score_list = get_emotion_score_list(recognized_face_list)
                    logging.debug('%s %s' % ("emotion_score_list",emotion_score_list))
                    mouth_score_list = get_mouth_score_list(conn_id,recognized_face_list)
                    logging.debug('%s %s' % ("mouth_score_list",mouth_score_list))
                    eyes_score_list = get_eyes_score_list(conn_id,recognized_face_list)
                    logging.debug('%s %s' % ("eyes_score_list",eyes_score_list))
                    hands_up_score_list = get_hands_up_score_list(conn_id,recognized_face_list, 0 if 'hands_up_count' not in summary else summary['hands_up_count'])
                    logging.debug('%s %s' % ("hands_up_score_list",hands_up_score_list))
                    concentration_score_list =[ round((x[0]*concentration_weight['head_yaw']+ x[1]*concentration_weight['head_pitch']+x[2]*concentration_weight['emotion']+x[3]*concentration_weight['eyes'])/100,2) for x in  zip(headpose_score_list_by_yaw,headpose_score_list_by_pitch,emotion_score_list,eyes_score_list)]
                    logging.debug('%s %s' % ("concentration_score_list",concentration_score_list))
                    vitality_score_list =[ round((x[0]*vitality_weight['emotion']+ x[1]*vitality_weight['mouth']+x[2]*vitality_weight['eyes']+x[3]*vitality_weight['hands'])/100,2) for x in  zip(emotion_score_list,mouth_score_list,eyes_score_list,hands_up_score_list)]
                    logging.debug('%s %s' % ("vitality_score_list",vitality_score_list))
                    
                    for i in range(len(recognized_face_list)):
                        recognized_face_list[i]['behavior']['concentration'] = concentration_score_list[i]
                        recognized_face_list[i]['behavior']['vitality'] = vitality_score_list[i]
                    summary['faces'] = recognized_face_list + not_recognized_face_list

                # is wonderful
                if len(summary['faces']) >= wonderful_face_count_threshold:
                    if 'hands_up_count' in summary and summary['hands_up_count'] / len(summary['faces']) >= wonderful_hands_up_pct:
                        
                        summary['is_wonderful'] = 1
                        
                        logging.debug('====wonderful hands up=========%d' % orgimg_fn)
                        logging.debug('%s' % summary['hands_up_count'])
                        logging.debug('%d' % len( summary['faces'] ))
                        cv2.imwrite('wonderful/'+orgimg_fn+'.png',orgimg)
                        cv2.imwrite('wonderful/'+orgimg_fn+'.jpg',orgimg)
                    else:
                        positive_count = len([1 for x in summary['faces'] if x['emotion']['primary'] == 'happy' ])
                        if positive_count / len(summary['faces']) >= wonderful_emotion_pct:
                            summary['is_wonderful'] = 1
                            orgimg_fn = str(random.random())
                            logging.debug('====wonderful happy========= % d' % orgimg_fn)
                            logging.debug('%d' % len([1 for x in summary['faces'] if x['emotion']['primary'] == 'happy' ]))
                            logging.debug('%d' % len( summary['faces'] ))
                        
                            cv2.imwrite('wonderful/'+orgimg_fn+'.png',orgimg)
                            cv2.imwrite('wonderful/'+orgimg_fn+'.jpg',orgimg)

        summary.setdefault('time_used',0)
        summary.setdefault('result_code',0)
        summary.setdefault('result_msg',"success")
        summary.setdefault('request_id',self.request_id)
        if self.get_argument("conn_id",None,True) == None:
            del summary['is_wonderful']




        for face in summary["faces"]:
            rect = face["face_rectangle"]
            emotidraw.draw_face_rect(orgimg,rect["left"],rect["top"],rect["width"],rect["height"],face["emotion"]["primary"])
            emotidraw.draw_behavior(orgimg,face)
            emotidraw.draw_landmark(orgimg,face)


        for i in range(len(feature_list)):
            if feature_list[i] == "BODY":
                 bodyservice.draw_kps(img,response_list[i])
        

        pre, ext = os.path.splitext(orgimg_fn)
        orgimg_fn = pre + '.jpg'


        cv2.imwrite('draw/face/'+orgimg_fn,orgimg)
        # cv2.imwrite('draw/hands640/'+orgimg_fn,img)



        

 
        # global save_counter
        # save_counter += 1
        # # if save_counter%600 ==0:
        # logging.debug("==save==",mouth_dist.shape)
        # target =  'om'
        # np.save('npy/'+target+'/mouth_dist',mouth_dist)
        # np.save('npy/'+target+'/mouth_dist_pct',mouth_dist_pct)
        # np.save('npy/'+target+'/eyes_dist',eyes_dist)
        # np.save('npy/'+target+'/eyes_dist_pct',eyes_dist_pct)

        # logging.debug(mouth_dist,mouth_dist_pct,eyes_dist,eyes_dist_pct)
        self.write(summary)




class BodyHandler(tornado.web.RequestHandler):
    def write_error(self, status_code, **kwargs):
        self.set_header('Content-Type', 'application/json')
        logging.debug(self._reason)
        # logging.debug(self.request.body)
        self.finish(json.dumps({
            'error': status_code,
            'message': self._reason,
        }))

    async def post(self):
        img = ""
        img_bytes = ""
        if "image_binary" in self.request.files:
            fileinfo = self.request.files['image_binary'][0]
            img_bytes = fileinfo["body"]           
        else :
            raise tornado.web.HTTPError(status_code=400,reason="No Image Input")

        feature_list = []
        request_list = []
        feature_list.append("BODY")
        start = time.time()
        request_list.append(bodyservice.do_infer(fileinfo["body"]))
        response_list = await multi(request_list)   

        summary = {}
        for i in range(len(feature_list)):
            if feature_list[i] == "BODY":
                summary['hands_up_count'] = bodyservice.parse_result(response_list[i])
                summary.setdefault('time_used',int((time.time()-start)*1000))
                summary.setdefault('result_code',0)
                summary.setdefault('result_msg',"success")
        
        # logging.debug("done")
        self.write(summary)

class SleepHandler(tornado.web.RequestHandler):
    async def post(self):
        await gen.sleep(3)
        self.write('hello\n')


def verify_threshold(data):
    global threshold_set
    try:
        if set(data.keys()) == threshold_set:
            if data['mouth_open_threshold'] < 0 :
                return False
            if data['face_height_threshold_for_mouth_status'] <=0 :
                return False
            # if data["eye_eyebrow_dist_ratio_threshold"] < 0:
            #     return False
            if data['eyes_open_threshold_l'] <0 :
                return False
            if data['eyes_open_threshold_m'] <0 :
                return False
            if data['eyes_open_threshold_s'] <0 :
                return False
            if data['large_face_height_lower_bound_for_eyes_status'] <0 :
                return False
            if data['middle_face_height_lower_bound_for_eyes_status'] <0 :
                return False
        else:
            return False
    except Exception as e: 
        print(e)
        return False
    return True

    

class ThresholdHandler(tornado.web.RequestHandler):
    def write_error(self, status_code, **kwargs):
        self.set_header('Content-Type', 'application/json')
        logging.debug(self._reason)
        # logging.debug(self.request.body)
        self.finish(json.dumps({
            'error': status_code,
            'message': self._reason,
        }))

    async def put(self): 
        data = escape.json_decode(self.request.body)
        data = data['threshold']
        print(data)
        if verify_threshold(data):
            global threshold
            threshold = data
            # print(data.keys())
            json_data = json.dumps(threshold, indent=4, sort_keys=True)
            f = open("threshold.json","w")
            f.write(json_data)
            f.close()
            self.write({
                'time_used':0,
                'result_code':0,
                'result_msg':"success",
                'request_id':str(uuid.uuid4()),
            })
        else:
            self.write({
                "request_id":str(uuid.uuid4()),
                "message": "This threshold setting is unacceptable.",
                "error": "BAD_REQUEST",
            })


    async def get(self): 
        global threshold
        self.write({
            'time_used':0,
            'result_code':0,
            'result_msg':"success",
            'request_id':str(uuid.uuid4()),
            'threshold':threshold,
        })

def make_app():
    return tornado.web.Application([
        (r"/emotibot/v2/analyze", MainHandler),
        (r"/emotibot/v2/draw", DrawHandler),
        (r"/emotibot/analyzebody", BodyHandler),
        (r"/sleep",SleepHandler),
        (r"/emotibot/threshold",ThresholdHandler),
    ],autoreload=True)

if __name__ == "__main__":
    with open('threshold.json') as f:
        data = json.load(f)
        threshold = data
    app = make_app()
    app.listen(int(os.environ['GATEWAY_PORT']))
    logging.debug("app is listen on port %s" % os.environ['GATEWAY_PORT'])
    tornado.autoreload.watch("threshold.json")
    tornado.ioloop.IOLoop.current().start() 