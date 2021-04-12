import json
import os
import re
import requests
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
from .utils import *

BILIBILI = os.path.expanduser("~/.kusa/bilibili.json")
BANGUMI_API = 'http://bangumi.bilibili.com/web_api/timeline_global'

class Bangumi:
    def __init__(self, **kwargs):
        self.api = kwargs['bot_api']

    async def execute_async(self, message):
        msg = message['raw_message']
        group = str(message.get("group_id", ''))
        user = str(message.get("user_id", 0))

        if msg == '订阅番剧更新':
            bilibilidata = loadjson(BILIBILI)
            if group in bilibilidata['bangumi_subscribe_groups']:
                return '本群已订阅番剧更新'
            else:
                bilibilidata['bangumi_subscribe_groups'].append(group)
                dumpjson(bilibilidata, BILIBILI)
                return '订阅番剧更新成功'

        if msg == '取消订阅番剧更新':
            bilibilidata = loadjson(BILIBILI)
            if group in bilibilidata['bangumi_subscribe_groups']:
                bilibilidata['bangumi_subscribe_groups'].remove(group)
                dumpjson(bilibilidata, BILIBILI)
                return '取消订阅番剧更新成功'
            else:
                return '本群未订阅番剧更新'

        if '什么时候更新' in msg:
            t = re.sub('什么时候更新', '', msg)
            if t == '':
                return None
            res = json.loads(requests.get(BANGUMI_API).text)['result']
            now = int(datetime.now().timestamp())
            for i in res:
                for s in i['seasons']:
                    if now > s['pub_ts']:
                        continue
                    if t in s['title']:
                        return '{} 下一集 {} 将于 {} {} 更新\n{}'.format(
                            s['title'], s['pub_index'], i['date'], s['pub_time'], s['url']
                        )
            return '我不知道'

        return None


    def jobs(self):
        trigger = CronTrigger(minute='*/5')
        job = (trigger, self.get_anime_update)
        return (job,)


    async def get_anime_update(self):
        sends = []
        bilibilidata = loadjson(BILIBILI)
        groups = bilibilidata['bangumi_subscribe_groups']
        res = json.loads(requests.get(BANGUMI_API).text)['result']
        now = int(datetime.now().timestamp())
        for i in res:
            delta = now - i['date_ts']
            if delta > 86400 or delta < 0:
                continue
            for s in i['seasons']:
                delta = abs(now - s['pub_ts'])
                if delta < 150:
                    if '僅限' in s['title']:
                        continue
                    msg = '{} {} {} {} 更新了!\n{}\n[CQ:image,file={}]'.format(
                        i['date'], s['pub_time'], s['title'], s['pub_index'],
                        s['url'], s['square_cover']
                    )
                    for g in groups:
                        sends.append({
                            "message_type": "group",
                            "group_id": g,
                            "message": msg
                        })

        return sends
