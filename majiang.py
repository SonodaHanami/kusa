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

MS_PPW_3 = 'https://ak-data-2.sapk.ch/api/v2/pl3/player_records/{}/{}/1262304000000?limit=1&mode=21,22,23,24,25,26&descending=true'
MS_PPW_4  = 'https://ak-data-2.sapk.ch/api/v2/pl4/player_records/{}/{}/1262304000000?limit=1&mode=8,9,11,12,15,16&descending=true'
TH_NODOCCHI = 'https://nodocchi.moe/api/listuser.php?name={}&start={}'

API_URL = {
    '3': MS_PPW_3,
    '4': MS_PPW_4,
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

        self.majsoul = Majsoul()
        self.tenhou  = Tenhou()

    async def execute_async(self, message):
        msg = message['raw_message']
        group = str(message.get('group_id', ''))
        user = str(message.get('user_id', 0))

        if msg == '订阅麻将':
            madata = loadjson(MAJIANG)
            if group in madata['subscribe_groups']:
                return '本群已订阅麻将'
            else:
                madata['subscribe_groups'].append(group)
                dumpjson(madata, MAJIANG)
                return '订阅麻将成功'

        if msg == '取消订阅麻将':
            madata = loadjson(MAJIANG)
            if group in madata['subscribe_groups']:
                madata['subscribe_groups'].remove(group)
                dumpjson(madata, MAJIANG)
                return '取消订阅麻将成功'
            else:
                return '本群未订阅麻将'

        prm = re.match('(怎么)?绑定 *雀魂(.*)', msg, re.I)
        if prm:
            usage = '使用方法：\n绑定雀魂 雀魂牌谱屋数字ID'
            success = '绑定{}成功'
            try:
                if prm[1]:
                    return usage
                id = str(int(prm[2]))
                madata = loadjson(MAJIANG)
                # 之前已经绑定过
                if madata['majsoul']['subscribers'].get(user):
                    old_id = madata['majsoul']['subscribers'][user]
                    if old_id != id:
                        madata['majsoul']['players'][old_id]['subscribers'].remove(user)
                        if not madata['majsoul']['players'][old_id]['subscribers']:
                            del madata['majsoul']['players'][old_id]
                        success += f'\n已自动解除绑定{old_id}'
                madata['majsoul']['subscribers'][user] = id
                if madata['majsoul']['players'].get(id):
                    madata['majsoul']['players'][id]['subscribers'].append(user)
                    madata['majsoul']['players'][id]['subscribers'] = list(set(madata['majsoul']['players'][id]['subscribers']))
                else:
                    madata['majsoul']['players'][id] = {
                        '3': {
                            'last_start_time': 0,
                            'rank': 0
                        },
                        '4': {
                            'last_start_time': 0,
                            'rank': 0
                        },
                        'subscribers': [user]
                    }
                dumpjson(madata, MAJIANG)
                return success.format(id)
            except:
                return usage

        if msg == '解除绑定雀魂':
            madata = loadjson(MAJIANG)
            if madata['majsoul']['subscribers'].get(user):
                id = madata['majsoul']['subscribers'][user]
                madata['majsoul']['players'][id]['subscribers'].remove(user)
                if not madata['majsoul']['players'][id]['subscribers']:
                    del madata['majsoul']['players'][id]
                del madata['majsoul']['subscribers'][user]
                dumpjson(madata, MAJIANG)
                return f'解除绑定{id}成功'
            else:
                return '没有找到你的绑定记录'

        prm = re.match('(怎么)?绑定 *天凤(.*)', msg, re.I)
        if prm:
            usage = '使用方法：\n绑定天凤 天凤ID'
            success = '绑定{}成功'
            try:
                if prm[1]:
                    return usage
                id = prm[2].strip()
                if not id:
                    return usage
                madata = loadjson(MAJIANG)
                # 之前已经绑定过
                if madata['tenhou']['subscribers'].get(user):
                    old_id = madata['tenhou']['subscribers'][user]
                    if old_id != id:
                        madata['tenhou']['players'][old_id]['subscribers'].remove(user)
                        if not madata['tenhou']['players'][old_id]['subscribers']:
                            del madata['tenhou']['players'][old_id]
                        success += f'\n已自动解除绑定{old_id}'
                madata['tenhou']['subscribers'][user] = id
                if madata['tenhou']['players'].get(id):
                    madata['tenhou']['players'][id]['subscribers'].append(user)
                    madata['tenhou']['players'][id]['subscribers'] = list(set(madata['tenhou']['players'][id]['subscribers']))
                else:
                    madata['tenhou']['players'][id] = {
                        'last_start_time': 0,
                        'subscribers': [user]
                    }
                dumpjson(madata, MAJIANG)
                return success.format(id)
            except:
                return usage

        if msg == '解除绑定天凤':
            madata = loadjson(MAJIANG)
            if madata['tenhou']['subscribers'].get(user):
                id = madata['tenhou']['subscribers'][user]
                madata['tenhou']['players'][id]['subscribers'].remove(user)
                if not madata['tenhou']['players'][id]['subscribers']:
                    del madata['tenhou']['players'][id]
                del madata['tenhou']['subscribers'][user]
                dumpjson(madata, MAJIANG)
                return f'解除绑定{id}成功'
            else:
                return '没有找到你的绑定记录'

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
        news = await self.majsoul.get_news_async() + await self.tenhou.get_news_async()
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

class Majsoul:
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
        for p in madata['majsoul']['players']:
            for m in ['3', '4']:
                if madata['majsoul']['players'][p][m]['last_start_time'] >= now - 1200:
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

                if j[0] and j[0].get('startTime') > madata['majsoul']['players'][p][m]['last_start_time']:
                    print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), p, m, '发现最近比赛更新！')
                    match = j[0]
                    madata['majsoul']['players'][p][m]['last_start_time'] = match.get('startTime')
                    tosend = []
                    start_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(match.get('startTime')))
                    duration = match.get('endTime') - match.get('startTime')
                    mode = GAME_MODE.get(match.get('modeId'), '未知')
                    subscriber = '不知道是谁'
                    for mp in match.get('players'):
                        mp['nickname'] = '{} {}'.format(ZONE_TAG.get(self.get_account_zone(mp['accountId'])), mp['nickname'])
                        if str(mp['accountId']) == p:
                            subscriber = mp['nickname']
                    tosend.append('雀魂雷达动叻！')
                    tosend.append('{} 打了一局 [{}]'.format(subscriber, mode))
                    tosend.append('开始时间: {}'.format(start_time))
                    tosend.append('持续时间: {}分{}秒'.format(duration // 60, duration % 60))
                    players = []
                    wind = 0
                    for mp in match.get('players'):
                        wind += 1
                        score = mp['score'] + len(match.get('players')) - wind
                        players.append((mp['nickname'], score))
                    players.sort(key=lambda i: i[1], reverse=True)
                    for mp in players:
                        rank = '[{}位]'.format(players.index(mp) + 1)
                        wind = '东南西北'[mp[1] % 10]
                        score = str(mp[1] // 10 * 10)
                        mp_result = [rank, wind, mp[0], score]
                        if score < 0:
                            mp_result.append('飞了！')
                        tosend.append(' '.join(mp_result))

                    msg = '\n'.join(tosend)
                    news.append(
                        {
                            'message': msg,
                            'user'   : madata['majsoul']['players'][p]['subscribers']
                        }
                    )

                    # 只有比赛更新才会有段位变动
                    cur_rank = 0
                    pname = '不知道是谁'
                    for mp in match.get('players'):
                        if str(mp['accountId']) == p:
                            cur_rank = mp['level'] // 100 % 10 * 10 + mp['level'] % 10
                            pname = mp['nickname']
                            break
                    pre_rank = madata['majsoul']['players'][p][m]['rank']
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
                                'user'   : madata['majsoul']['players'][p]['subscribers']
                            })
                        else:
                            pass
                        madata['majsoul']['players'][p][m]['rank'] = cur_rank

                else:
                    # print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), p, m, '没有发现最近比赛更新')
                    pass

        dumpjson(madata, MAJIANG)

        print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), f'雀魂雷达扫描到了{len(news)}个新事件')

        for msg in news:
            msg['target_groups'] = []
            for u in msg['user']:
                for g in memberdata:
                    if u in memberdata[g] and g not in msg['target_groups']:
                        msg['target_groups'].append(g)

        return news

class Tenhou:
    async def get_news_async(self):
        '''
        返回最新消息
        '''
        news = []
        madata = loadjson(MAJIANG)
        memberdata = loadjson(MEMBER)
        now = int(datetime.now().timestamp())
        print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), '天凤雷达开始扫描')
        for p in madata['tenhou']['players']:
            if madata['tenhou']['players'][p]['last_start_time'] >= now - 1200:
                continue
            try:
                # print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), p, '请求天凤玩家最近比赛')
                j = requests.get(TH_NODOCCHI.format(p, madata['tenhou']['players'][p]['last_start_time'] + 1)).json()
            except Exception as e:
                print(e)
                continue
            if not j or not j.get('list'):
                # print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), p, '没有发现最近比赛更新')
                continue

            if j['list'][-1] and int(j['list'][-1].get('starttime')) > madata['tenhou']['players'][p]['last_start_time']:
                print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), p, '发现最近比赛更新！')
                match = j['list'][-1]
                madata['tenhou']['players'][p]['last_start_time'] = int(match.get('starttime'))
                tosend = []
                start_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(match.get('starttime'))))
                duration = match.get('during')
                bar = ''
                mode = ''
                if match.get('playernum') == '3':
                    mode += '三'
                elif match.get('playernum') == '4':
                    mode += '四'
                else:
                    mode += bar
                pl = int(match.get('playerlevel'))
                if match.get('shuugi'):
                    pl += 4
                if match.get('sctype') == 'e' and int(match.get('playlength')) == 0:
                    mode += '技'
                    mode += bar
                else:
                    mode += '般上特鳳若銀琥孔'[pl]
                    mode += '技東南'[int(match.get('playlength'))]
                mode += '喰' if match.get('kuitanari') else bar
                mode += '赤' if match.get('akaari') else bar
                mode += '祝' +  '０１２３４５６７８９'[int(match.get('shuugi'))] if match.get('shuugi') else bar
                mode += '速' if match.get('rapid') else ''
                subscriber = p
                tosend.append('天凤雷达动叻！')
                tosend.append('{} 打了一局 [{}]'.format(subscriber, mode))
                tosend.append('开始时间: {}'.format(start_time))
                tosend.append('持续时间: {}分'.format(duration))
                players = []
                for mp in ['player1', 'player2', 'player3', 'player4'][:int(match.get('playernum'))]:
                    rank = '[{}位]'.format(mp[-1])
                    score = match.get(mp + 'ptr')
                    mp_result = [rank, match.get(mp), score]
                    tosend.append(' '.join(mp_result))

                msg = '\n'.join(tosend)
                news.append(
                    {
                        'message': msg,
                        'user'   : madata['tenhou']['players'][p]['subscribers']
                    }
                )

            else:
                # print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), p, '没有发现最近比赛更新')
                pass

        dumpjson(madata, MAJIANG)

        print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), f'天凤雷达扫描到了{len(news)}个新事件')

        for msg in news:
            msg['target_groups'] = []
            for u in msg['user']:
                for g in memberdata:
                    if u in memberdata[g] and g not in msg['target_groups']:
                        msg['target_groups'].append(g)

        return news
