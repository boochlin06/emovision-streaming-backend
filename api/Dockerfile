FROM python:3.6.2
ENV PYTHONUNBUFFERED 1
RUN mkdir /docker_api
WORKDIR /docker_api
COPY . /docker_api
RUN pip install  -i https://pypi.tuna.tsinghua.edu.cn/simple -r  streamingAnalyzer/requirements-opencv.txt
RUN apt-get install curl
HEALTHCHECK --interval=5m --timeout=10s \
    CMD curl --include --no-buffer \
        --header "Connection: close" \
        --header "Upgrade: Upgrade" \
        http://localhost:5050/streaming/check