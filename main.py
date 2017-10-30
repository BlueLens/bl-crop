from __future__ import print_function
import uuid

import os
from google.cloud import bigquery

import uuid
import logging
import redis
import json
import stylelens_index
from bluelens_spawning_pool import spawning_pool

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

AWS_BUCKET = 'bluelens-style-object'

TMP_CROP_IMG_FILE = './tmp.jpg'

CWD_PATH = os.getcwd()


HOST_URL = 'host_url'
TAG = 'tag'
SUB_CATEGORY = 'sub_category'
PRODUCT_NAME = 'product_name'
IMAGE_URL = 'image_url'
PRODUCT_PRICE = 'product_price'
CURRENCY_UNIT = 'currency_unit'
PRODUCT_URL = 'product_url'
PRODUCT_NO = 'product_no'
MAIN = 'main'
NATION = 'nation'

SPAWNING_CRITERIA = 10

REDIS_IMAGE_CROP_QUEUE = 'bl:image:crop:queue'

api_instance = stylelens_index.ImageApi()

REDIS_SERVER = os.environ['REDIS_SERVER']
SUBSCRIBE_TOPIC = os.environ['SUBSCRIBE_TOPIC']

AWS_ACCESS_KEY = os.environ['AWS_ACCESS_KEY']
AWS_SECRET_ACCESS_KEY = os.environ['AWS_SECRET_ACCESS_KEY']

logging.basicConfig(filename='./log/main.log', level=logging.DEBUG)
rconn = redis.StrictRedis(REDIS_SERVER, port=6379)

def job(info):
  site_code = info['code']
  print(site_code)
  logging.debug(site_code)

  client = bigquery.Client.from_service_account_json(
      'BlueLens-d8117bd9e6b1.json')

  # query = 'SELECT * FROM stylelens.' + site_code
  query = 'SELECT * FROM stylelens.8seconds LIMIT 30'

  query_job = client.run_async_query(str(uuid.uuid4()), query)

  query_job.begin()
  query_job.result()  # Wait for job to complete.

  # Print the results.
  destination_table = query_job.destination
  destination_table.reload()
  i = 0
  for row in destination_table.fetch_data():
    image_info = stylelens_index.Image()
    image_info.host_url = str(row[0])
    image_info.tags = str(row[1]).split(',')
    image_info.product_name = str(row[3])
    image_info.image_url = str(row[4])
    image_info.product_price = str(row[5])
    image_info.currency_unit = str(row[6])
    image_info.product_url = str(row[7])
    image_info.product_no = str(row[8])
    image_info.main = int(row[9])
    image_info.nation = str(row[10])
    image_info.bucket = AWS_BUCKET

    push_image_to_queue(image_info)

    if i % SPAWNING_CRITERIA == 0:
      spawn_cropper(str(uuid.uuid4()))
    i = i + 1

def push_image_to_queue(image_info):
  image_json_str = image_class_to_json_str(image_info)
  rconn.lpush(REDIS_IMAGE_CROP_QUEUE, image_json_str)

def image_class_to_json_str(image):
  image_dic = {}
  image_dic['name'] = image.name
  image_dic['host_url'] = image.host_url
  image_dic['host_code'] = image.host_code
  image_dic['tags'] = image.tags
  image_dic['format'] = image.format
  image_dic['product_name'] = image.product_name
  image_dic['parent_image_raw'] = image.parent_image_raw
  image_dic['parent_image_mobile'] = image.parent_image_mobile
  image_dic['parent_image_mobile_thumb'] = image.parent_image_mobile_thumb
  image_dic['image'] = image.image
  image_dic['class_code'] = image.class_code
  image_dic['bucket'] = image.bucket
  image_dic['storage'] = image.storage
  image_dic['product_price'] = image.product_price
  image_dic['currency_unit'] = image.currency_unit
  image_dic['product_url'] = image.product_url
  image_dic['product_no'] = image.product_no
  image_dic['main'] = image.main
  image_dic['nation'] = image.nation

  s = json.dumps(image_dic)
  print(s)
  return s


def spawn_cropper(uuid):

  pool = spawning_pool.SpawningPool()

  project_name = 'bl-cropper-' + uuid
  print('spawn_cropper: ' + project_name)

  pool.setServerUrl('bl-mem-store-master')
  pool.setApiVersion('v1')
  pool.setKind('Pod')
  pool.setMetadataName(project_name)
  pool.setMetadataNamespace('index')
  pool.addMetadataLabel('name', project_name)
  container = pool.createContainer()
  pool.setContainerName(container, project_name)
  pool.addContainerEnv(container, 'AWS_ACCESS_KEY', AWS_ACCESS_KEY)
  pool.addContainerEnv(container, 'AWS_SECRET_ACCESS_KEY', AWS_SECRET_ACCESS_KEY)
  pool.addContainerEnv(container, 'REDIS_SERVER', REDIS_SERVER)
  pool.setContainerImage(container, 'bluelens/bl-cropper:latest')
  pool.addContainer(container)
  pool.setRestartPolicy('Never')
  pool.spawn()

def sub(rconn):
  logging.debug('start subscription')

  pubsub = rconn.pubsub()
  pubsub.subscribe([SUBSCRIBE_TOPIC])

  for item in pubsub.listen():
    data = item['data']
    logging.debug(data)
    print(data)

    try:
      if (type(data) is bytes):
        d = json.loads(item['data'].decode('utf-8'))
        job(d)
      elif (type(data) is str):
        d = json.loads(data)
        job(d)
    except ValueError:
      print("wait subscribe")

if __name__ == '__main__':
  sub(rconn)
