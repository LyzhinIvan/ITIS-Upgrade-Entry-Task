FROM ubuntu:16.04

RUN apt-get update && apt-get install -y python3 python3-pip
RUN ln -s /usr/bin/python3 /usr/bin/python
RUN ln -s /usr/bin/pip3 /usr/bin/pip

WORKDIR /opt/
COPY parser parser
COPY webapp webapp

RUN pip install -r parser/requirements.txt
RUN pip install -r webapp/requirements.txt

EXPOSE 5000

ENV FLASK_APP server.py
ENV MONGO_HOST mongo
ENV LC_ALL=C.UTF-8 
ENV LANG=C.UTF-8

CMD cd parser && \
    python parser_mongo.py --logs-file=/opt/logs.txt && \
    cd ../webapp && \
    flask run --host=0.0.0.0