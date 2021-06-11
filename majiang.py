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

SANMA = 'https://ak-data-2.sapk.ch/api/v2/pl3/player_records/{}/{}/1262304000000?limit=1&mode=21,22,23,24,25,26&descending=true'
SIMA  = 'https://ak-data-2.sapk.ch/api/v2/pl4/player_records/{}/{}/1262304000000?limit=1&mode=8,9,11,12,15,16&descending=true'

API_URL = {
    '3': SANMA,
    '4': SIMA,
}

GAME_MODE = {
    8:  '金之间 四人东',
    9:  '金之间 四人南',
    11: '玉之间 四人东',
    12: '玉之间 四人南',
    15: '王座之间 四人东',
    16: '王座之间 四人南',
    21: '金之间 三人东',
    22: '金之间 三人南',
    23: '玉之间 三人东',
    24: '玉之间 三人南',
    25: '王座之间 三人东',
    26: '王座之间 三人南',
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
        for p in madata['players']:
            for m in ['3', '4']:
                if madata['players'][p]['last_start_time'][m] >= now - 1200 or datetime.now().minute % 10 != 0:
                    continue
                try:
                    print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), p, m, '请求雀魂玩家最近比赛')
                    end_of_today = int(datetime.now().replace(hour=23, minute=59, second=59).timestamp()) * 1000 + 999
                    j = requests.get(API_URL[m].format(p, end_of_today)).json()
                except Exception as e:
                    print(e)
                    continue
                if not j:
                    print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), p, m, '没有发现任何比赛')
                    continue

                new_match = False
                if j[0]['startTime'] > madata['players'][p]['last_start_time'][m]:
                    print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), p, m, '发现最近比赛更新！')
                    madata['players'][p]['last_start_time'][m] = j[0]['startTime']
                    match = j[0]
                    tosend = []
                    start_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(match['startTime']))
                    duration = match['endTime'] - match['startTime']
                    mode = GAME_MODE.get(match['modeId'], '未知')
                    subscriber = '不知道是谁'
                    for mp in match['players']:
                        if str(mp['accountId']) == p:
                            subscriber = mp['nickname']
                            break
                    tosend.append('雀魂雷达动叻！')
                    tosend.append('{} 打了一局 [{}]'.format(subscriber, mode))
                    tosend.append('开始时间: {}'.format(start_time))
                    tosend.append('持续时间: {}分{}秒'.format(duration // 60, duration % 60))
                    players = []
                    wind = 0
                    for mp in match['players']:
                        wind += 1
                        score = mp['score'] + len(match['players']) - wind
                        players.append((mp['nickname'], score))
                    players.sort(key=lambda i: i[1], reverse=True)
                    for mp in players:
                        rank = '[{}位]'.format(players.index(mp) + 1)
                        wind = '东南西北'[mp[1] % 10]
                        score = str(mp[1] // 10 * 10)
                        mp_result = [rank, wind, mp[0], score]
                        if mp[1] < 0:
                            mp_result.append('飞了！')
                        tosend.append(' '.join(mp_result))

                    m = '\n'.join(tosend)
                    news.append(
                        {
                            'message': m,
                            'user'   : madata['players'][p]['subscribers']
                        }
                    )
                else:
                    print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), p, m, '没有发现最近比赛更新')

        dumpjson(madata, MAJIANG)

        for msg in news:
            msg['target_groups'] = []
            for u in msg['user']:
                for g in memberdata:
                    if u in memberdata[g] and g not in msg['target_groups']:
                        msg['target_groups'].append(g)

        return news
