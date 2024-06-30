import os
import time
import threading
import pysnooper
import logging
import time, json, datetime
import pika
import urllib
import urllib.parse
import requests, json
from requests.auth import HTTPBasicAuth

class Rabbit_Producer():

    def __init__(self, host=os.environ.get('RABBIT_HOST', '127.0.0.1'), port=5672, user='admin', password='admin',
                 virtual_host='/'):  # 默认端口5672，可不写
        credentials = pika.PlainCredentials(user, password)
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=host, port=port, credentials=credentials, virtual_host=virtual_host,
                                      heartbeat=10))  # virtual_host='/'
        self.channel = self.connection.channel()  # 声明一个管道
        self.properties = pika.BasicProperties(  # 需要将消息发送到exchange，exchange会把消息分发给queue。queue会把消息分发给消费者
            delivery_mode=2,  # 消息持久化
            # content_type='application/json',
            # content_encoding='UTF-8',
            # priority=0,
            # expiration = '60000000'    # 有效时间，毫秒为单位
        )
        self.exchange_name = ""
        self.exchange_type = ""
        self.queue_name = ""

    # 设置广播通道
    def set_exchange(self, exchange='predict-exchange', exchange_type='topic'):
        self.exchange_name = exchange
        self.exchange_type = exchange_type
        # 注意：这里是广播，不需要声明queue
        self.channel.exchange_declare(exchange=exchange, exchange_type=exchange_type, durable=True)  # 声明广播管道
        if exchange_type == 'direct':
            self.set_queue()
        self.channel.basic_qos(prefetch_count=1)  # 一个消费者只同时处理一个数据
        logging.info('set rabbit exchange %s, type %s' % (exchange, exchange_type))

    # 注意：在直连模式下，设置队列，需要设置队列，此时不启动广播器exchange，其他情况不要设置队列
    def set_queue(self, queue_name='predict-queue'):
        self.queue_name = queue_name
        self.channel.queue_declare(queue=queue_name, durable=True)

    # 发送消息，传递字节流
    def send_message(self, message, rout_key="predict-key"):
        # logging.info('send to rabbit: time is %s' % datetime.datetime.now())
        self.channel.basic_publish(exchange=self.exchange_name, routing_key=rout_key, body=message,
                                   properties=self.properties)  # body消息内容

    # 删除exchange,  因为有时exchange会弄错
    def delete_exchange(self, exchange_name=None):
        if not exchange_name:
            exchange_name = self.exchange_name
        self.channel.exchange_delete(exchange_name)

    # 关闭，要记得关闭信道
    def close(self):
        self.channel.close()
        self.connection.close()


class Rabbit_Consumer():

    def __init__(self, host=os.environ.get('RABBIT_HOST', '127.0.0.1'), port=5672, user='admin', password='admin',
                 virtual_host='/'):  # 默认端口5672，可不写
        credentials = pika.PlainCredentials(user, password)
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=host, port=port, credentials=credentials, virtual_host=virtual_host,
                                      heartbeat=10))
        self.channel = self.connection.channel()  # 声明一个管道
        self.exchange_name = ""
        self.exchange_type = ""
        self.queue_name = ""

    # 设置广播接收队列.  exchange通过路由规则发送到符合路由规则的队列。用户订阅队列，就能收到该队列的消息。
    def set_queue(self, exchange='predict-exchange', exchange_type='topic', queue_name='predict-queue',
                  rout_key="predict-key"):
        self.exchange_name = exchange
        self.exchange_type = exchange_type
        self.queue_name = queue_name
        if (exchange):
            # 声明转发器
            self.channel.exchange_declare(exchange=exchange, exchange_type=exchange_type, durable=True)
            # 发送方和接收方不知道谁首先连接到RabbitMQ，双方连接上来都先声明一个队列
            self.channel.queue_declare(queue=queue_name, durable=True)
            # queue绑定到转发器上
            self.channel.queue_bind(exchange=exchange, queue=queue_name,
                                    routing_key=rout_key)  # 如果是fanout，rout_key要设置成""
            self.channel.basic_qos(prefetch_count=1)  # 一个消费者只同时处理一个数据
            logging.info('set rabbit queue %s bing to exchange %s' % (queue_name, exchange))
        else:
            print('====', exchange)
            self.channel.queue_declare(queue=queue_name, durable=True)

    # 设置消息接收配置
    def set_receive_config(self, callback, auto_ack=True):
        # 声明接收收消息变量。#callback收到消息后执行的回调函数。no_ack默认不执行回复ack，以便服务器宕机，能被其他消费者接收
        self.channel.basic_consume(on_message_callback=callback, queue=self.queue_name, auto_ack=auto_ack)

    # 开始接收消息，不停循环接收，没有消息挂起等待
    def start_receive(self):
        logging.info('start listening')
        self.channel.start_consuming()

    def close(self):
        self.channel.close()
        self.connection.close()


class Rabbit_info():
    def __init__(self, host=os.environ.get('RABBIT_HOST', '127.0.0.1'), port=15672, user='admin', password='admin'):
        self.url = 'http://' + host + ':' + str(port) + '/api/'
        self.user = user
        self.password = password

    def get_queue(self):
        response = requests.get(self.url + "queues", auth=HTTPBasicAuth(self.user, self.password))
        queues = json.loads(response.text)
        print(json.dumps(queues, indent=4))
        allqueue = []
        for queue in queues:
            queue_temp = {}
            queue_temp['name'] = queue['name']  # 队列名称
            queue_temp['auto_delete'] = queue['auto_delete']  # 是否自动删除
            queue_temp['consumers'] = queue['consumers']  # 队列后的消费者数目
            queue_temp['durable'] = queue['durable']  # 是否持久化
            queue_temp['memory'] = queue['memory'] / 1024 / 1024  # 占用内存MB
            queue_temp['state'] = queue['state']  # 状态
            queue_temp['vhost'] = queue['vhost']  # 命名空间
            queue_temp['message_count'] = queue['reductions']  # 消息数量
            if 'message_stats' in queue:  # 没有消费者的话是没有message消息的
                queue_temp['message_stats:ack'] = queue['message_stats']['ack']
                queue_temp['message_stats:deliver'] = queue['message_stats']['deliver']
                queue_temp['message_stats:deliver_get'] = queue['message_stats']['deliver_get']
                queue_temp['message_stats:deliver_no_ack'] = queue['message_stats']['deliver_no_ack']
                queue_temp['message_stats:get'] = queue['message_stats']['get']
                queue_temp['message_stats:get_no_ack'] = queue['message_stats']['get_no_ack']
                queue_temp['message_stats:redeliver'] = queue['message_stats']['redeliver']

            allqueue.append(queue_temp)
        return allqueue

    # 不能获取历史数据，只能获取未被消费的数据
    def get_message(self, vhost, queue_name, count=50):
        # ack_requeue_true 让消息重新排队
        data = {"count": count, "ackmode": "ack_requeue_true", "encoding": "auto", "truncate": 50000}
        header = {
            'Content-Type': 'application/json'
        }

        vhost = urllib.parse.quote(vhost, 'utf-8')
        url = self.url + "queues/" + vhost + "/" + queue_name + "/get"
        # print(url)
        response = requests.post(url, json=data, headers=header, auth=HTTPBasicAuth(self.user, self.password))

        message = json.loads(response.text)
        return message

    def get_msg_count(self):
        try:
            url = self.url + "queues/%2f/predict-queue"
            response = requests.get(url, auth=HTTPBasicAuth(self.user, self.password))
            result = json.loads(response.text)
            # print(result)
            return result['backing_queue_status']['len']
        except Exception as e:
            # print(e)
            print('消费队列还未建立')
            return -1

    def get_node(self):
        response = requests.get(self.url + "nodes", auth=HTTPBasicAuth(self.user, self.password))
        nodes = json.loads(response.text)
        return nodes

    def get_exchange(self):
        response = requests.get(self.url + "exchanges", auth=HTTPBasicAuth(self.user, self.password))
        exchanges = json.loads(response.text)
        return exchanges

    def get_channel(self):
        response = requests.get(self.url + "channels", auth=HTTPBasicAuth(self.user, self.password))
        channels = json.loads(response.text)
        return channels

    def get_user(self):
        response = requests.get(self.url + "users", auth=HTTPBasicAuth(self.user, self.password))
        users = json.loads(response.text)
        return users



