import redis
import json
import time

r = redis.Redis(host='localhost', port=6379, db=0)
p = r.pubsub()
p.subscribe('machine_A_data')

for message in p.listen():
    print(message)