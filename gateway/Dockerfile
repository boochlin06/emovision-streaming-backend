FROM python:3.6.2
WORKDIR /app
ADD requirements.txt .

# RUN pip install --upgrade pip
RUN pip install  -i https://pypi.tuna.tsinghua.edu.cn/simple -r  requirements.txt
# RUN pip install  -r  requirements.txt

ADD ./ .

# CMD  tail -f /dev/null

CMD ["python","server.py","--log-level","debug"]
HEALTHCHECK --interval=300s --timeout=12s --start-period=30s \  
 CMD ./docker-healthcheck