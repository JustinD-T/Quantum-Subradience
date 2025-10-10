import redis
import time
import json
r = redis.Redis(host='localhost', port=6379, db=0)
machine_id = 'machine_A'
print(f"[{machine_id}] Starting data collection...")
count = 0
while True:
    count += 1
    data = {'count' : count}
    time.sleep(1)

    json_data = json.dumps(data)

    r.publish(f'{machine_id}_data', json_data)