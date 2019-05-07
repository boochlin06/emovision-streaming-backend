import cv2

strokeWidth = 1
emojiSize = 40
emotionTypeList = ["angry","confused","contempt","disgust","fear","happy","neutral","sad","surprise"]
lengthInSecond = 1

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


emojiMap = {}
for emotion in emotionTypeList:
    emojiMap[emotion] = cv2.imread("emoji/"+emotion+".png", cv2.IMREAD_UNCHANGED)
    emojiMap[emotion] = cv2.resize(emojiMap[emotion],(emojiSize,emojiSize),cv2.INTER_CUBIC)

def _myOverlay(src,dst,x,y):
    # print(src.shape)
    if x < 0 or (x + src.shape[0]) > (dst.shape[1]-1) or y < 0 or (y+src.shape[1]) > (dst.shape[1]-1):
        return
    # print(x,x+src.shape[0],y,y+src.shape[1])
    alpha_s = src[:,:,3]
    alpha_l = 1.0 - alpha_s
    for i in range(0,src.shape[0]):
        for j in range(0,src.shape[1]):
            for k in range(0,3):
                if (alpha_s[i][j]!=0):
                    dst[x+i][y+j][k]= src[i][j][k]

def draw_face_rect(img,left,top,width,height,primary_emotion):
    cv2.rectangle(img, (left,top), (left + width,top + height), emotionColorMap[primary_emotion])
    
def draw_face_emoji(img,left,top,width,height,primary_emotion):
    _myOverlay(emojiMap[primary_emotion],img,top- emojiSize - strokeWidth,left+int((width-emojiSize)/2))
    