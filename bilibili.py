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
