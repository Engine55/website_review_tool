import os
import redis
import multiprocessing
from rq import Worker, Queue, Connection

listen = ['high', 'default', 'low']
# listen = ['high']

redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')

conn = redis.from_url(redis_url)

if __name__ == '__main__':
    # multiprocessing.set_start_method('spawn')
    with Connection(conn):
        worker = Worker(map(Queue, listen))
        worker.work()
