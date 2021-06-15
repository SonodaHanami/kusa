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

PLAYER_RANK = {
    1: '初心',
    2: '雀士',
    3: '雀杰',
    4: '雀豪',
    5: '雀圣',
    6: '魂天',
}

ZONE_TAG = {
    0: '',
    1: 'Ⓒ',
    2: 'Ⓙ',
    3: 'Ⓔ',
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
        trigger = CronTrigger(minute='*/10', second='50')
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

    def get_account_zone(self, account_id):
        if not account_id:
            return 0
        prefix = account_id >> 23
        if 0 <= prefix <= 6:
            return 1
        if 7 <= prefix <= 12:
            return 2
        if 13 <= prefix <= 15:
            return 3
        return 0

    async def get_news_async(self):
        '''
        返回最新消息
        '''
        news = []
        madata = loadjson(MAJIANG)
        memberdata = loadjson(MEMBER)
        now = int(datetime.now().timestamp())
        print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), '雀魂雷达开始扫描')
        for p in madata['players']:
            for m in ['3', '4']:
                if madata['players'][p][m]['last_start_time'] >= now - 1200:
                    continue
                try:
                    # print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), p, m, '请求雀魂玩家最近比赛')
                    end_of_today = int(datetime.now().replace(hour=23, minute=59, second=59).timestamp()) * 1000 + 999
                    j = requests.get(API_URL[m].format(p, end_of_today)).json()
                except Exception as e:
                    print(e)
                    continue
                if not j:
                    # print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), p, m, '没有发现任何比赛')
                    continue

                new_match = False
                if j[0]['startTime'] > madata['players'][p][m]['last_start_time']:
                    print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), p, m, '发现最近比赛更新！')
                    madata['players'][p][m]['last_start_time'] = j[0]['startTime']
                    match = j[0]
                    tosend = []
                    start_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(match['startTime']))
                    duration = match['endTime'] - match['startTime']
                    mode = GAME_MODE.get(match['modeId'], '未知')
                    subscriber = '不知道是谁'
                    for mp in match['players']:
                        mp['nickname'] = '{} {}'.format(ZONE_TAG.get(self.get_account_zone(mp['accountId'])), mp['nickname'])
                        if str(mp['accountId']) == p:
                            subscriber = mp['nickname']
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

                    msg = '\n'.join(tosend)
                    news.append(
                        {
                            'message': msg,
                            'user'   : madata['players'][p]['subscribers']
                        }
                    )

                    # 只有比赛更新才会有段位变动
                    cur_rank = 0
                    pname = '不知道是谁'
                    for mp in match['players']:
                        if str(mp['accountId']) == p:
                            cur_rank = mp['level'] // 100 % 10 * 10 + mp['level'] % 10
                            pname = mp['nickname']
                            break
                    pre_rank = madata['players'][p][m]['rank']
                    if cur_rank != pre_rank:
                        if cur_rank:
                            if pre_rank:
                                word = '升' if cur_rank > pre_rank else '掉'
                                msg = '{} 的{}段位从{}{}{}到了{}{}'.format(
                                    pname,
                                    '零一二三四'[int(m)] + '麻',
                                    PLAYER_RANK[pre_rank // 10], pre_rank % 10 or '',
                                    word,
                                    PLAYER_RANK[cur_rank // 10], cur_rank % 10 or ''
                                )
                            else:
                                msg = '{} 的{}段位达到了{}{}'.format(
                                    pname,
                                    '零一二三四'[int(m)] + '麻',
                                    PLAYER_RANK[cur_rank // 10],
                                    cur_rank % 10 or ''
                                )
                            news.append({
                                'message': msg,
                                'user'   : madata['players'][p]['subscribers']
                            })
                        else:
                            pass
                        madata['players'][p][m]['rank'] = cur_rank

                else:
                    # print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), p, m, '没有发现最近比赛更新')
                    pass

        dumpjson(madata, MAJIANG)

        for msg in news:
            msg['target_groups'] = []
            for u in msg['user']:
                for g in memberdata:
                    if u in memberdata[g] and g not in msg['target_groups']:
                        msg['target_groups'].append(g)

        return news
