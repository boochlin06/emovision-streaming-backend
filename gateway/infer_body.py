import tensorflow as tf
from tensorflow_serving.apis import predict_pb2
from tensorflow_serving.apis import prediction_service_pb2_grpc
import cv2
import numpy as np
import grpc
import sys
import time
import os
import matplotlib.pyplot as plt


from tornado.ioloop import IOLoop
from tornado.gen import Future
import math


_channel = None
_channel_pool = []
_channel_index = 0
_url_list = None
kps_lines = [(1, 2), (0, 1), (0, 2), (2, 4), (1, 3), (6, 8), (8, 10), (5, 7), (7, 9), (12, 14), (14, 16), (11, 13), (13, 15), (5, 6), (11, 12)]

def _fwrap(f, gf):
    try:
        f.set_result(gf.result())
    except Exception as e:
        f.set_exception(e)

def fwrap(gf, ioloop=None):
    '''
        Wraps a GRPC result in a future that can be yielded by tornado
        
        Usage::
        
            @coroutine
            def my_fn(param):
                result = yield fwrap(stub.function_name.future(param, timeout))
        
    '''
    f = Future()

    if ioloop is None:
        ioloop = IOLoop.current()

    gf.add_done_callback(lambda _: ioloop.add_callback(_fwrap, f, gf))
    return f



def initBodyServiceClient():
    global _channel_pool  # add this line!
    global _url_list
    if len(_channel_pool) == 0 : # see notes below; explicit test for None
        _url_list = os.environ['BODY_SERVICE_URL_LIST'].split(" ")
        for i in range (len(_url_list)):
            print(_url_list[i])
            _channel_pool.append(grpc.insecure_channel(_url_list[i]))
        print("channel connected")
    else:
        raise RuntimeError("_channel has already been set.")


def isHandsup(kps,sc=.1,threshold=10):
    # print('kps',kps.shape,kps)
    sh_coordinates = np.array((0.,0.))
    shoulders = [5,6]
    # 7:l_elbow 8: r_elbow ,9: l_wrist 10: r_wrist
    body_kps = [7,8,9,10]
    _succeed_count = 0
    
    # cal the shoulders
    for shoulder in shoulders:
        if kps[2,shoulder] > sc:
            _succeed_count+=1
            sh_coordinates+= kps[:2,shoulder]
            sh_coordinates = sh_coordinates/_succeed_count
    # print(sh_coordinates) 
    
    # return False if no shoulder can be calculated
    if sh_coordinates[1] == 0:
        return False
    # return True if any keypoint is lower sh_coordinate
    for val_kp in body_kps:
        
        if kps[2,val_kp] > sc and kps[1,val_kp]+ threshold  < sh_coordinates[1]:
#             print(val_kp,kps[2,val_kp],sc,kps[1,val_kp],sh_coordinates[1])
            return True
    #  return False if no keypoint is lower sh_coordinate    
    return False           

def isHandsupV2(kps,sc=.1,threshold=10):

    # hands_up = False
    # if right hand confidence enough
    if kps[2,10] > sc and kps[2,8] > sc:
        # if hand point up
        if kps[1,10] < kps[1,8]:
            # if degree enough
            if kps[0,8] == kps[0,10]:
                return True
            deg = abs(math.degrees(math.atan((kps[1,8]-kps[1,10])/(kps[0,8]-kps[0,10]))))
            # print(deg)
            if deg > 50:
                return True

    if kps[2,9] > sc and kps[2,7] > sc:
        # if hand point up
        if kps[1,9] < kps[1,7]:
            # if degree enough
            if kps[0,7] == kps[0,9]:
                return True
            deg = abs(math.degrees(math.atan((kps[1,7]-kps[1,9])/(kps[0,7]-kps[0,9]))))
            # print(deg)
            if deg > 50:
                return True
    return False      

def isHandsupV3(kps):
    if isHandsup(kps) or isHandsupV2(kps):
        return True
    else:
        return False

def do_infer(image_binary):
    # channel = grpc.insecure_channel(os.environ['BODY_SERVICE_URL_LIST'])
    global _channel_pool 
    global _channel_index
    global _url_list
    stub = None
    index = _channel_index
    _channel_index = (_channel_index + 1)% len(_url_list)
    # print("using index ",index)
    try:
        stub = prediction_service_pb2_grpc.PredictionServiceStub(_channel_pool[index])
    except:
        # _channel = grpc.insecure_channel(os.environ['BODY_SERVICE_URL_LIST'])
        _channel_pool[index] = grpc.insecure_channel(_url_list[index])
        stub = prediction_service_pb2_grpc.PredictionServiceStub(_channel_pool[index])

    req = predict_pb2.PredictRequest()
    req.inputs["inputs"].CopyFrom(
         tf.contrib.util.make_tensor_proto(image_binary,shape=[1])
    )
    # results = stub.Predict.future(req,10)
    results = stub.Predict.future(req,45)
    return fwrap(results)

def parse_result(results):
    # print("results",results)
    try:
        kp_resuts = tf.make_ndarray(results.outputs["keypoints"])
        if len(kp_resuts) == 0:
            return 0
        else:
            total = sum(list(map(lambda _row: isHandsupV3(_row),kp_resuts)))
            
            return total
    except:
        return 0


def draw_kps(img_np,results):
    print("img_np.shape",img_np.shape)
    print("img_np[0][0].shape",img_np[0][0].shape)
    bbox = tf.make_ndarray(results.outputs["bbox_coordinates"])
    kp_resuts = tf.make_ndarray(results.outputs["keypoints"])


    # # crop out bounding boxes
    # org_image_list = []

    # for kp,b in zip(kp_resuts,bbox):
    #     org_image_list.append(np.copy(img_np[int(b[2]):int(b[3]),  int(b[0]):  int(b[1]), :]))
    
    # img_np[:,:,:]=np.zeros(img_np.shape)

    # for i,b in enumerate(bbox):
    #     img_np[int(b[2]):int(b[3]),  int(b[0]):  int(b[1]), :] = org_image_list[i]
        

     
    # draw keypoints 
    for kp,b in zip(kp_resuts,bbox):
        _det_img = img_np[int(b[2]):int(b[3]),  int(b[0]):  int(b[1]), :]
        plot_kp(_det_img,kp)
        
        


 

def plot_kp(det_img, kps, kp_thresh=0.4, alpha=1):
    
    # for i in range(17):

    #     p1 = (kps[0, i].astype(np.int32), kps[1, i].astype(np.int32))
    #     # cv2.circle(det_img, p1,radius=3, color=(0,0,255), thickness=-1, lineType=cv2.LINE_AA)
    #     # cv2.putText(det_img, p1,radius=3, color=(0,0,255), thickness=-1, lineType=cv2.LINE_AA)
    #     cv2.putText(det_img, str(i), p1, cv2.FONT_HERSHEY_SIMPLEX,0.5, (0,0,255), 1, cv2.LINE_AA)
    cmap = plt.get_cmap('rainbow')
    colors = [cmap(i) for i in np.linspace(0, 1, len(kps_lines) + 2)]
    colors = [(c[2] * 255, c[1] * 255, c[0] * 255) for c in colors]

    v1 = isHandsup(kps)
    v2 = isHandsupV2(kps)
    if v1 or v2:

        my_color = None
        if v1 and v2:
            my_color = (255,255,255)
        elif v1 and (not v2):
            my_color = (0,255,0)
        elif v2 and (not v1):
            my_color = (0,0,255)
            

        mid_shoulder = (
            kps[:2, 5] +
            kps[:2, 6]) / 2.0
        sc_mid_shoulder = np.minimum(
            kps[2, 5],
            kps[2, 6])
        mid_hip = (
            kps[:2, 11] +
            kps[:2, 12]) / 2.0
        sc_mid_hip = np.minimum(
            kps[2, 11],
            kps[2, 12])
        nose_idx = 0
        if sc_mid_shoulder > kp_thresh and kps[2, nose_idx] > kp_thresh:
            cv2.line(
                det_img, tuple(mid_shoulder.astype(np.int32)), tuple(kps[:2, nose_idx].astype(np.int32)),
                color=my_color, thickness=2, lineType=cv2.LINE_AA)
        if sc_mid_shoulder > kp_thresh and sc_mid_hip > kp_thresh:
            cv2.line(
                det_img, tuple(mid_shoulder.astype(np.int32)), tuple(mid_hip.astype(np.int32)),
                color=my_color, thickness=2, lineType=cv2.LINE_AA)
        
        # Draw the keypoints.
        for l in range(len(kps_lines)):
            i1 = kps_lines[l][0]
            i2 = kps_lines[l][1]
            p1 = kps[0, i1].astype(np.int32), kps[1, i1].astype(np.int32)
            p2 = kps[0, i2].astype(np.int32), kps[1, i2].astype(np.int32)
            if kps[2, i1] > kp_thresh and kps[2, i2] > kp_thresh:
                cv2.line(
                    det_img, p1, p2,
                    color=my_color, thickness=2, lineType=cv2.LINE_AA)
            if kps[2, i1] > kp_thresh:
                cv2.circle(
                    det_img, p1,
                    radius=3, color=my_color, thickness=-1, lineType=cv2.LINE_AA)
            if kps[2, i2] > kp_thresh:
                cv2.circle(
                    det_img, p2,
                    radius=3, color=my_color, thickness=-1, lineType=cv2.LINE_AA)
    else:

        mid_shoulder = (
            kps[:2, 5] +
            kps[:2, 6]) / 2.0
        sc_mid_shoulder = np.minimum(
            kps[2, 5],
            kps[2, 6])
        mid_hip = (
            kps[:2, 11] +
            kps[:2, 12]) / 2.0
        sc_mid_hip = np.minimum(
            kps[2, 11],
            kps[2, 12])
        nose_idx = 0
        if sc_mid_shoulder > kp_thresh and kps[2, nose_idx] > kp_thresh:
            cv2.line(
                det_img, tuple(mid_shoulder.astype(np.int32)), tuple(kps[:2, nose_idx].astype(np.int32)),
                color=colors[len(kps_lines)], thickness=2, lineType=cv2.LINE_AA)
        if sc_mid_shoulder > kp_thresh and sc_mid_hip > kp_thresh:
            cv2.line(
                det_img, tuple(mid_shoulder.astype(np.int32)), tuple(mid_hip.astype(np.int32)),
                color=colors[len(kps_lines) + 1], thickness=2, lineType=cv2.LINE_AA)
        
        # Draw the keypoints.
        for l in range(len(kps_lines)):
            i1 = kps_lines[l][0]
            i2 = kps_lines[l][1]
            p1 = kps[0, i1].astype(np.int32), kps[1, i1].astype(np.int32)
            p2 = kps[0, i2].astype(np.int32), kps[1, i2].astype(np.int32)
            if kps[2, i1] > kp_thresh and kps[2, i2] > kp_thresh:
                cv2.line(
                    det_img, p1, p2,
                    color=colors[l], thickness=2, lineType=cv2.LINE_AA)
            if kps[2, i1] > kp_thresh:
                cv2.circle(
                    det_img, p1,
                    radius=3, color=colors[l], thickness=-1, lineType=cv2.LINE_AA)
            if kps[2, i2] > kp_thresh:
                cv2.circle(
                    det_img, p2,
                    radius=3, color=colors[l], thickness=-1, lineType=cv2.LINE_AA)
