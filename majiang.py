import json
import os
import random
import re
import requests
import time
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
from random import randint as ri
from .utils import *

CONFIG = load_config()
ADMIN = CONFIG['ADMIN']
MAJIANG = os.path.expanduser('~/.kusa/majiang.json')
MEMBER = os.path.expanduser('~/.kusa/member.json')

SANMA = 'https://ak-data-2.sapk.ch/api/v2/pl3/player_records/{}/{}/1262304000000?limit=1&mode=22&descending=true'

GAME_MODE = {
    22: '三麻'
}

class Majiang:
    def __init__(self, **kwargs):
        self.api = kwargs['bot_api']

    async def execute_async(self, message):
        msg = message['raw_message']
        group = str(message.get("group_id", ''))
        user = str(message.get("user_id", 0))

        return None

    def jobs(self):
        trigger = CronTrigger(minute='*', second='50')
        job = (trigger, self.send_news_async)
        return (job,)

    async def send_news_async(self):
        madata = loadjson(MAJIANG)
        groups = madata.get('subscribe_groups')
        if not groups:
            return None
        news = await self.get_news_async()
        sends = []
        for msg in news:
            for g in groups:
                if str(g) in msg['target_groups']:
                    sends.append({
                        'message_type': 'group',
                        'group_id': g,
                        'message': msg['message']
                    })
        return sends

    async def get_news_async(self):
        '''
        返回最新消息
        '''
        news = []
        madata = loadjson(MAJIANG)
        memberdata = loadjson(MEMBER)
        now = int(datetime.now().timestamp())
        # print('{} 请求玩家状态更新 {}'.format(datetime.now(), sids))
        for p in madata['players']:
            if madata['players'][p]['last_start_time'] >= now - 1200 or datetime.now().minute % 10 != 0:
                continue
            try:
                print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), '请求雀魂玩家最近比赛', p)
                end_of_today = int(datetime.now().replace(hour=23, minute=59, second=59).timestamp()) * 1000 + 999
                j = requests.get(SANMA.format(p, end_of_today)).json()
            except Exception as e:
                print(e)
                continue
            if not j:
                continue

            new_match = False
            if j[0]['startTime'] > madata['players'][p]['last_start_time']:
                print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), p, '发现最近比赛更新！')
                madata['players'][p]['last_start_time'] = j[0]['startTime']
                match = j[0]
                tosend = []
                start_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(match['startTime']))
                duration = match['endTime'] - match['startTime']
                mode = GAME_MODE.get(match['modeId'], '未知')
                tosend.append('雀魂雷达动叻！')
                tosend.append('开始时间: {}'.format(start_time))
                tosend.append('持续时间: {:.0f}分{:.0f}秒'.format(duration / 60, duration % 60))
                tosend.append('游戏模式: {}'.format(mode))
                players = [(pp['nickname'], pp['score']) for pp in match['players']]
                players.sort(key=lambda i: i[1], reverse=True)
                for name, score in players:
                    tosend.append('{} {}'.format(name, score))

                m = '\n'.join(tosend)
                news.append(
                    {
                        'message': m,
                        'user'   : madata['players'][p]['subscribers']
                    }
                )
            else:
                print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), p, '没有发现最近比赛更新')

        dumpjson(madata, MAJIANG)

        for msg in news:
            msg['target_groups'] = []
            for u in msg['user']:
                for g in memberdata:
                    if u in memberdata[g] and g not in msg['target_groups']:
                        msg['target_groups'].append(g)

        return news
