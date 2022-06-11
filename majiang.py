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

START = 1262303999
MS_PPW_RECORDS_3 = 'https://ak-data-2.sapk.ch/api/v2/pl3/player_records/{}/{}999/{}999?limit=100&mode=21,22,23,24,25,26&descending=true&tag=100'
MS_PPW_RECORDS_4  = 'https://ak-data-2.sapk.ch/api/v2/pl4/player_records/{}/{}999/{}999?limit=100&mode=8,9,11,12,15,16&descending=true&tag=100'
MS_PPW_STATS_3 = 'https://ak-data-2.sapk.ch/api/v2/pl3/player_stats/{}/{}999/{}999?mode=21,22,23,24,25,26&tag={}'
MS_PPW_STATS_4 = 'https://ak-data-2.sapk.ch/api/v2/pl4/player_stats/{}/{}999/{}999?mode=8,9,11,12,15,16&tag={}'
TH_NODOCCHI = 'https://nodocchi.moe/api/listuser.php?name={}&start={}'

PPW_RECORDS = {
    '3': MS_PPW_RECORDS_3,
    '4': MS_PPW_RECORDS_4,
}

PPW_STATS = {
    '3': MS_PPW_STATS_3,
    '4': MS_PPW_STATS_4,
}

DEFAULT_DATA = {
    'subscribe_groups': [],
    'majsoul': {
        'subscribers': {},
        'players': {}
    },
    'tenhou': {
        'subscribers': {},
        'players': {}
    },
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

RANK_SCORE = {
    21: 600,
    22: 800,
    23: 1000,
    31: 1200,
    32: 1400,
    33: 2000,
    41: 2800,
    42: 3200,
    43: 3600,
    51: 4000,
    52: 6000,
    53: 9000,
    60: 65536
}

ZONE_TAG = {
    0: '',
    1: 'Ⓒ',
    2: 'Ⓙ',
    3: 'Ⓔ',
}

class Majiang:
    def __init__(self, **kwargs):
        print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), '初始化Majiang', end=' ')

        self.api = kwargs['bot_api']
        self.majsoul = Majsoul()
        self.tenhou = Tenhou()
        self.MINUTE = (datetime.now() + timedelta(minutes=2)).minute
        self.DONE = False

        if not os.path.exists(MAJIANG):
            dumpjson(DEFAULT_DATA, MAJIANG)

        print(f'完成！MINUTE={self.MINUTE}')

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
            result = '绑定{}'
            try:
                if prm[1]:
                    return usage
                pid = str(int(prm[2]))
                madata = loadjson(MAJIANG)
                await self.api.send_group_msg(
                    group_id=message['group_id'],
                    message=f'正在尝试绑定并初始化玩家信息',
                )
                # 之前已经绑定过
                if madata['majsoul']['subscribers'].get(user):
                    old_id = madata['majsoul']['subscribers'][user]
                    if old_id != pid:
                        del madata['majsoul']['subscribers'][user]
                        madata['majsoul']['players'][old_id]['subscribers'].remove(user)
                        if not madata['majsoul']['players'][old_id]['subscribers']:
                            del madata['majsoul']['players'][old_id]
                        result = f'已自动解除绑定{old_id}\n' + result
                if madata['majsoul']['players'].get(pid):
                    madata['majsoul']['subscribers'][user] = pid
                    madata['majsoul']['players'][pid]['subscribers'].append(user)
                    madata['majsoul']['players'][pid]['subscribers'] = list(set(madata['majsoul']['players'][pid]['subscribers']))
                    result += '成功，玩家信息已存在，跳过初始化'
                else:
                    try:
                        rank = self.majsoul.get_player_rank(pid)
                        if rank:
                            result += '成功\n'
                            madata['majsoul']['subscribers'][user] = pid
                            madata['majsoul']['players'][pid] = {
                                'nickname': rank['nickname'],
                                '3': {
                                    'last_end': rank['end_3'],
                                    'rank': rank['rank_3'],
                                    'score': rank['score_3'],
                                },
                                '4': {
                                    'last_end': rank['end_4'],
                                    'rank': rank['rank_4'],
                                    'score': rank['score_4'],
                                },
                                'subscribers': [user]
                            }
                        else:
                            result += '失败\n'
                        result += self.majsoul.get_rank_message(rank)
                    except Exception as e:
                        result += '失败\n初始化玩家信息失败'
                        print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), '初始化玩家信息失败', e)
                dumpjson(madata, MAJIANG)
                memberdata = loadjson(MEMBER)
                if group not in madata['subscribe_groups']:
                    result += '\nWARNING: 本群未订阅麻将，即使绑定成功也不会播报该玩家的比赛结果'
                if not memberdata.get(group) or not memberdata[group].get(user):
                    result += '\nWARNING: 你不在群友列表中，即使绑定成功也不会播报该玩家的比赛结果'
                return result.format(pid)
            except Exception as e:
                print(e)
                return usage

        if msg == '解除绑定雀魂':
            madata = loadjson(MAJIANG)
            if madata['majsoul']['subscribers'].get(user):
                pid = madata['majsoul']['subscribers'][user]
                madata['majsoul']['players'][pid]['subscribers'].remove(user)
                if not madata['majsoul']['players'][pid]['subscribers']:
                    del madata['majsoul']['players'][pid]
                del madata['majsoul']['subscribers'][user]
                dumpjson(madata, MAJIANG)
                return f'解除绑定{pid}成功'
            else:
                return '没有找到你的绑定记录'

        if msg == '查询群友的雀魂段位':
            # await self.api.send_group_msg(
            #     group_id=message['group_id'],
            #     message=f'正在查询',
            # )
            madata = loadjson(MAJIANG)
            memberdata = loadjson(MEMBER)
            players_in_group = []
            for qq, pid in madata['majsoul']['subscribers'].items():
                if qq in memberdata[group]:
                    players_in_group.append(pid)
            players_in_group = list(set(players_in_group))
            replys = []
            for pid in players_in_group:
                # rank = self.majsoul.get_player_rank(pid)
                rank = {
                    'pid': pid,
                    'nickname': madata['majsoul']['players'][pid]['nickname'],
                    'rank_3': madata['majsoul']['players'][pid]['3']['rank'],
                    'rank_4': madata['majsoul']['players'][pid]['4']['rank'],
                    'score_3': madata['majsoul']['players'][pid]['3']['score'],
                    'score_4': madata['majsoul']['players'][pid]['4']['score'],
                }
                if rank:
                    replys.append(self.majsoul.get_rank_message(rank))
            replys.sort()
            if len(replys) > 2:
                replys.append('大家都有光明的未来！')
            if replys:
                return '\n'.join(replys)
            else:
                return '查不到哟'
        prm = re.match('(怎么)?绑定 *天凤(.*)', msg, re.I)
        if prm:
            usage = '使用方法：\n绑定天凤 天凤ID'
            result = '绑定{}成功'
            try:
                if prm[1]:
                    return usage
                pid = prm[2].strip()
                if not pid:
                    return usage
                madata = loadjson(MAJIANG)
                # 之前已经绑定过
                if madata['tenhou']['subscribers'].get(user):
                    old_id = madata['tenhou']['subscribers'][user]
                    if old_id != pid:
                        del madata['tenhou']['subscribers'][user]
                        madata['tenhou']['players'][old_id]['subscribers'].remove(user)
                        if not madata['tenhou']['players'][old_id]['subscribers']:
                            del madata['tenhou']['players'][old_id]
                        result += f'\n已自动解除绑定{old_id}'
                madata['tenhou']['subscribers'][user] = pid
                if madata['tenhou']['players'].get(pid):
                    madata['tenhou']['players'][pid]['subscribers'].append(user)
                    madata['tenhou']['players'][pid]['subscribers'] = list(set(madata['tenhou']['players'][pid]['subscribers']))
                else:
                    madata['tenhou']['players'][pid] = {
                        'last_end': 0,
                        'subscribers': [user]
                    }
                dumpjson(madata, MAJIANG)
                memberdata = loadjson(MEMBER)
                if group not in madata['subscribe_groups']:
                    result += '\nWARNING: 本群未订阅麻将，即使绑定成功也不会播报该玩家的比赛结果'
                if not memberdata.get(group) or not memberdata[group].get(user):
                    result += '\nWARNING: 你不在群友列表中，即使绑定成功也不会播报该玩家的比赛结果'
                return result.format(pid)
            except:
                return usage

        if msg == '解除绑定天凤':
            madata = loadjson(MAJIANG)
            if madata['tenhou']['subscribers'].get(user):
                pid = madata['tenhou']['subscribers'][user]
                madata['tenhou']['players'][pid]['subscribers'].remove(user)
                if not madata['tenhou']['players'][pid]['subscribers']:
                    del madata['tenhou']['players'][pid]
                del madata['tenhou']['subscribers'][user]
                dumpjson(madata, MAJIANG)
                return f'解除绑定{pid}成功'
            else:
                return '没有找到你的绑定记录'

        return None

    def jobs(self):
        trigger = CronTrigger(minute='*', second='45')
        job = (trigger, self.send_news_async)
        trigger = CronTrigger(hour='5', minute='15')
        majsoul_check = (trigger, self.majsoul.check_rank)
        return (job, majsoul_check)

    async def send_news_async(self):
        minute = datetime.now().minute
        if minute == 0:
            self.DONE = False
        if self.DONE or minute != self.MINUTE:
            return None
        madata = loadjson(MAJIANG)
        groups = madata.get('subscribe_groups')
        if not groups:
            return None
        news = await self.majsoul.get_news_async()
        # news = await self.majsoul.get_news_async() + await self.tenhou.get_news_async()
        self.MINUTE = random.randint(0, 59)
        self.DONE = True
        sends = []
        print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), f'NEXT MINUTE={self.MINUTE}')
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
        prefix = int(account_id) >> 23
        if 0 <= prefix <= 6:
            return 1
        if 7 <= prefix <= 12:
            return 2
        if 13 <= prefix <= 15:
            return 3
        return 0

    def get_next_rank(self, rank, offset=1):
        ranks = list(RANK_SCORE.keys())
        if rank not in ranks:
            print('rank_invalid')
            return -1
        if rank == 21 and offset == -1:
            print('雀士1掉无可掉')
            return 21
        if rank == 53 and offset == 1:
            print('升上魂天！')
            return 60
        return ranks[ranks.index(rank) + offset]

    def get_player_rank(self, pid):
        now = int(datetime.now().timestamp())
        end_3, rank_3, score_3 = now, 0, 0
        end_4, rank_4, score_4 = now, 0, 0
        stats_3 = requests.get(MS_PPW_STATS_3.format(pid, START, now, now // 3600)).json()
        stats_4 = requests.get(MS_PPW_STATS_4.format(pid, START, now, now // 3600)).json()
        nickname = stats_3.get('nickname') or stats_4.get('nickname')
        if not nickname:
            return {}

        if stats_3.get('nickname'):
            records = requests.get(MS_PPW_RECORDS_3.format(pid, now, START)).json()
            if records and records[0] and records[0].get('startTime'):
                end_3 = records[0].get('startTime')
            rank_3 = stats_3['level']['id'] // 100 % 10 * 10 + stats_3['level']['id'] % 10
            score_3 = stats_3['level']['score'] + stats_3['level']['delta']
            if RANK_SCORE.get(rank_3):
                if score_3 > RANK_SCORE[rank_3]: # 升段
                    rank_3 = self.get_next_rank(rank_3)
                    score_3 = RANK_SCORE[rank_3] // 2
                if score_3 < 0: # 掉段
                    if rank_3 != 21:
                        rank_3 = self.get_next_rank(rank_3, -1)
                        score_3 = RANK_SCORE[rank_3] // 2
        if stats_4.get('nickname'):
            records = requests.get(MS_PPW_RECORDS_4.format(pid, now, START)).json()
            if records and records[0] and records[0].get('startTime'):
                end_4 = records[0].get('startTime')
            rank_4 = stats_4['level']['id'] // 100 % 10 * 10 + stats_4['level']['id'] % 10
            score_4 = stats_4['level']['score'] + stats_4['level']['delta']
            if RANK_SCORE.get(rank_4):
                if score_4 > RANK_SCORE[rank_4]: # 升段
                    rank_4 = self.get_next_rank(rank_4)
                    score_4 = RANK_SCORE[rank_4] // 2
                if score_4 < 0: # 掉段
                    if rank_4 != 21:
                        rank_4 = self.get_next_rank(rank_4, -1)
                        score_4 = RANK_SCORE[rank_4] // 2

        return {
            'pid': pid,
            'nickname': nickname,
            'end_3': end_3,
            'end_4': end_4,
            'rank_3': rank_3,
            'rank_4': rank_4,
            'score_3': score_3,
            'score_4': score_4,
        }

    def get_rank_message(self, rank_info):
        if not rank_info.get('nickname'):
            return '查无此人，请检查雀魂牌谱屋数字ID'
        s1 = '{} {}'.format(ZONE_TAG.get(self.get_account_zone(rank_info['pid'])), rank_info['nickname'])
        rank_3 = rank_info.get('rank_3', 0)
        rank_4 = rank_info.get('rank_4', 0)
        score_3 = rank_info.get('score_3', 0)
        score_4 = rank_info.get('score_4', 0)
        if rank_3:
            s3 = '三麻{}{}({}/{})'.format(
                PLAYER_RANK[rank_3 // 10],
                rank_3 % 10 or '',
                score_3,
                RANK_SCORE[rank_3]
            )
        else:
            s3 = '没有查询到三麻段位'
        if rank_4:
            s4 = '四麻{}{}({}/{})'.format(
                PLAYER_RANK[rank_4 // 10],
                rank_4 % 10 or '',
                score_4,
                RANK_SCORE[rank_4]
            )
        else:
            s4 = '没有查询到四麻段位'
        return '{}，{}，{}'.format(s1, s3, s4)

    def check_rank(self):
        print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), '自动校正雀魂玩家段位信息')
        madata = loadjson(MAJIANG)
        changed = False
        check_message = '将玩家{}的{}由{}校正为{}'
        for pid in madata['majsoul']['players']:
            rank = self.get_player_rank(pid)
            nickname = madata['majsoul']['players'][pid].get('nickname')
            if nickname != rank['nickname']:
                print(
                    datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'),
                    check_message.format(pid, 'nickname', nickname, rank['nickname'])
                )
                madata['majsoul']['players'][pid]['nickname'] = rank['nickname']
                changed = True
            if madata['majsoul']['players'][pid]['3']['rank'] != rank['rank_3']:
                print(
                    datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'),
                    check_message.format(pid, 'rank_3', madata['majsoul']['players'][pid]['3']['rank'], rank['rank_3'])
                )
                madata['majsoul']['players'][pid]['3']['rank'] = rank['rank_3']
                changed = True
            if madata['majsoul']['players'][pid]['3']['score'] != rank['score_3']:
                print(
                    datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'),
                    check_message.format(pid, 'score_3', madata['majsoul']['players'][pid]['3']['score'], rank['score_3'])
                )
                madata['majsoul']['players'][pid]['3']['score'] = rank['score_3']
                changed = True
            if madata['majsoul']['players'][pid]['4']['rank'] != rank['rank_4']:
                print(
                    datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'),
                    check_message.format(pid, 'rank_4', madata['majsoul']['players'][pid]['4']['rank'], rank['rank_4'])
                )
                madata['majsoul']['players'][pid]['4']['rank'] = rank['rank_4']
                changed = True
            if madata['majsoul']['players'][pid]['4']['score'] != rank['score_4']:
                print(
                    datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'),
                    check_message.format(pid, 'score_4', madata['majsoul']['players'][pid]['4']['score'], rank['score_4'])
                )
                madata['majsoul']['players'][pid]['4']['score'] = rank['score_4']
                changed = True
        if changed:
            dumpjson(madata, MAJIANG)
            print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), '校正完成')
        else:
            print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), '无事发生')

    async def get_news_async(self):
        '''
        返回最新消息
        '''
        news = []
        madata = loadjson(MAJIANG)
        memberdata = loadjson(MEMBER)
        now = int(datetime.now().timestamp())
        print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), '雀魂雷达开始扫描')
        for pid in madata['majsoul']['players']:
            for m in ['3', '4']:
                last_end = madata['majsoul']['players'][pid][m]['last_end']
                if last_end >= now - 1200:
                    continue
                try:
                    # print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), pid, m, '请求雀魂玩家最近比赛')
                    end_of_today = int(datetime.now().replace(hour=23, minute=59, second=59).timestamp())
                    url = PPW_RECORDS[m].format(pid, end_of_today, last_end)
                    records = requests.get(url).json()
                except Exception as e:
                    print(e)
                    continue
                if not records:
                    # print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), pid, m, '没有发现任何比赛')
                    continue

                # print(records)
                if records[0] and records[0].get('startTime') > last_end:
                    print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), pid, m, '发现最近比赛更新！', len(records))
                    match = j[0]
                    madata['majsoul']['players'][pid][m]['last_end'] = match.get('endTime')
                    tosend = []
                    start_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(match.get('startTime')))
                    duration = match.get('endTime') - match.get('startTime')
                    mode = GAME_MODE.get(match.get('modeId'), '未知')
                    for mp in match.get('players'):
                        mp['nickname'] = '{} {}'.format(ZONE_TAG.get(self.get_account_zone(mp['accountId'])), mp['nickname'])
                        if int(mp['accountId']) == int(pid):
                            subscriber = mp['nickname']
                    tosend.append('雀魂雷达动叻！')
                    tosend.append('{} 打了一局 [{}]'.format(subscriber, mode))
                    tosend.append('开始时间: {}'.format(start_time))
                    tosend.append('持续时间: {}分{}秒'.format(duration // 60, duration % 60))
                    players = []
                    wind = 0
                    playernum = len(match.get('players'))
                    for mp in match.get('players'):
                        wind += 1
                        score = mp['score'] + playernum - wind
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
                            'user'   : madata['majsoul']['players'][pid]['subscribers']
                        }
                    )

                    # 只有比赛更新才会有段位变动
                    cur_rank = 0
                    pname = '不知道是谁'
                    for mp in match.get('players'):
                        if str(mp['accountId']) == pid:
                            cur_rank = mp['level'] // 100 % 10 * 10 + mp['level'] % 10
                            pname = mp['nickname']
                            break
                    pre_rank = madata['majsoul']['players'][pid][m]['rank']
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
                                'user'   : madata['majsoul']['players'][pid]['subscribers']
                            })
                        else:
                            pass
                        madata['majsoul']['players'][pid][m]['rank'] = cur_rank

                else:
                    # print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), pid, m, '没有发现最近比赛更新')
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
        for pid in madata['tenhou']['players']:
            if madata['tenhou']['players'][pid]['last_end'] >= now - 1200:
                continue
            try:
                # print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), pid, '请求天凤玩家最近比赛')
                j = requests.get(TH_NODOCCHI.format(pid, madata['tenhou']['players'][pid]['last_end'] + 1)).json()
            except Exception as e:
                print(e)
                continue
            if not j or not j.get('list'):
                # print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), pid, '没有发现最近比赛更新')
                continue

            if j['list'][-1] and int(j['list'][-1].get('starttime')) > madata['tenhou']['players'][pid]['last_end']:
                print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), pid, '发现最近比赛更新！')
                match = j['list'][-1]
                madata['tenhou']['players'][pid]['last_end'] = int(match.get('starttime')) + int(match.get('during')) * 60
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
                subscriber = pid
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
                        'user'   : madata['tenhou']['players'][pid]['subscribers']
                    }
                )

            else:
                # print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), pid, '没有发现最近比赛更新')
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