FROM python:3.6.2
ENV PYTHONUNBUFFERED 1
ENV CELERY_BROKER_URL redis://redis:6379/0
ENV CELERY_RESULT_BACKEND redis://redis:6379/0
ENV C_FORCE_ROOT true

ENV HOST 0.0.0.0
ENV PORT 5001
ENV DEBUG true

COPY . /videoapi
WORKDIR /videoapi

# install requirements
RUN pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# expose the app port
EXPOSE 5001

RUN pip install -i https://pypi.tuna.tsinghua.edu.cn/simple gunicorn==19.3.0

# run the app server
CMD ["gunicorn", "--bind", "0.0.0.0:5001","--log-level","info","--reload","--timeout", "3600", "--workers", "3", "app:app"]

RUN apt-get install curl
HEALTHCHECK --interval=5m --timeout=10s \
    CMD curl -X GET http://localhost:5001//v1/videos
