import os
import time
from celery import Celery
from celery.utils.log import get_task_logger


CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://redis:6379'),
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://redis:6379')

celery = Celery('tasks', broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)

logger = get_task_logger(__name__)

@celery.task(name='tasks.analyze')
def analyze(inputPath):
    # filename = videos.save(requestFile)
    logger.info("task:")
    time.sleep(5)
    return os.path.abspath(__file__)