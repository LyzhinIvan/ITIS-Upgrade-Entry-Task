# ITIS Upgrade Entry Task

## Install and Run via Docker (simple way)
1) [Install Docker Compose](https://docs.docker.com/compose/install/)
2) From root of repository run `docker-compose up`

## Install and Run without Docker (hard way)
1) Install Python3.5+ and Pip
2) Install required Python packages  
```
  pip install -r parser/requirements.txt
  pip install -r webapp/requirements.txt
```
3) [Install MongoDB Community Edition](https://docs.mongodb.com/manual/administration/install-community/)
4) From `parser` folder run parsing with your logs file  
  `python parser_mongo.py --logs-file=<path-to-file-with-logs>`
5) Set environment variable  
  `FLASK_APP=server.py`
6) From `webapp` folder run server  
  `flask run`

Webapp is available at http://localhost:5000
