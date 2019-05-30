FROM valian/docker-python-opencv-ffmpeg:py3
ENV PYTHONUNBUFFERED 1
ENV CELERY_BROKER_URL redis://redis:6379/0
ENV CELERY_RESULT_BACKEND redis://redis:6379/0
ENV C_FORCE_ROOT true

COPY . /queue
WORKDIR /queue
RUN apt-get update
RUN apt-get install -y x264 ffmpeg
RUN pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
ENTRYPOINT celery -A tasks worker --loglevel=info