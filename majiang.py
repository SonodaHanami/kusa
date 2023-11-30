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

logger = get_logger('kusa')

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
    1: '🇨🇳 ',
    2: '🇯🇵 ',
    3: '🇺🇳 ',
}
if CONFIG.get('MAJSOUL_PLAYER_ZONE', False) != True:
    ZONE_TAG = {0:'', 1:'', 2:'', 3:''}

class Majiang:
    def __init__(self, **kwargs):
        logger.info('初始化Majiang 开始！')

        self.api = kwargs['bot_api']
        self.wi = kwargs['whois']
        self.majsoul = Majsoul()
        self.MINUTE = min(55, (datetime.now() + timedelta(minutes=2)).minute)
        self.DONE = False

        if not os.path.exists(MAJIANG):
            dumpjson(DEFAULT_DATA, MAJIANG)

        logger.info(f'初始化Majiang 完成！MINUTE={self.MINUTE}')

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

        prm = re.match('(怎么)?绑定 *雀魂(牌谱屋)?(.*)', msg, re.I)
        if prm:
            usage = 'https://docs.qq.com/sheet/DWG5uaFRrS0hjRlVL'
            result = '绑定{}'
            try:
                if prm[1]:
                    return usage
                pid = str(int(prm[3]))
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
                        logger.warning(f'初始化玩家信息失败 {e}')
                dumpjson(madata, MAJIANG)
                memberdata = loadjson(MEMBER)
                if group not in madata['subscribe_groups']:
                    result += '\nWARNING: 本群未订阅麻将，即使绑定成功也不会播报该玩家的比赛结果'
                if not memberdata.get(group) or not memberdata[group].get(user):
                    result += '\nWARNING: 你不在群友列表中，尝试把你自动加入群友列表\n'
                    info = await self.api.get_stranger_info(user_id=user)
                    nickname = info['nickname']
                    result += self.wi.add_alias(group, user, '我', nickname)
                return result.format(pid)
            except Exception as e:
                logger.warning(e)
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

        return None

    def jobs(self):
        trigger = CronTrigger(hour='9,18', minute='*/5')
        get_news = (trigger, self.get_news_async)
        trigger = CronTrigger(day_of_week='0', hour='12', minute='5')
        get_weekly_summary = (trigger, self.get_weekly_summary)
        return (get_news, get_weekly_summary)

    def get_message_node(self, user_id, message, name='放浪雀士'):
        return {
            'type': 'node',
            'data': {
                'name': name,
                'uin': user_id,
                'content': message,
            }
        }

    async def get_news_async(self):
        minute = datetime.now().minute
        if minute == 0:
            self.DONE = False
        if self.DONE or minute < self.MINUTE:
            return None
        madata = loadjson(MAJIANG)
        memberdata = loadjson(MEMBER)
        groups = madata.get('subscribe_groups')
        if not groups:
            return None
        # 获取登录号信息
        bot_info = {}
        try:
            bot_info = await self.api.get_login_info()
        except Exception as e:
            logger.warning(str(e))
        news = await self.majsoul.get_news_async(bot_info=bot_info)
        self.MINUTE = random.randint(0, 55)
        self.DONE = True
        logger.info(f'Majiang next MINUTE={self.MINUTE}')
        for group in madata['subscribe_groups']:
            messages = []
            players_in_group = []
            for qq in madata['majsoul']['subscribers']:
                if qq in memberdata[group]:
                    players_in_group.append(qq)
            for qq in players_in_group:
                for n in news.get(qq, []):
                    # 自己发自己的战报
                    messages.append(self.get_message_node(qq, n))
            # 仅在有更新时发送战报
            if len(messages) > 0:
                random.shuffle(messages)
                messages.reverse()
                # 获取bot登录信息让bot发，获取不到时让随机群友发
                messages.append(self.get_message_node(bot_info.get('user_id', random.choice(list(memberdata[group].keys()))), '雀魂雷达动叻！'))
                messages.reverse()
                await self.api.send_group_forward_msg(group_id=group, messages=messages)

    async def get_weekly_summary(self):
        # 获取登录号信息
        bot_info = {}
        try:
            bot_info = await self.api.get_login_info()
        except Exception as e:
            logger.warning(str(e))
        news = await self.majsoul.get_weekly_summary(bot_info=bot_info)
        memberdata = loadjson(MEMBER)
        for group, messages in news.items():
            await self.api.send_group_forward_msg(
                group_id=group,
                messages=[self.get_message_node(m['user_id'] or random.choice(list(memberdata[group].keys())), m['message']) for m in messages]
            )


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
            # 无效段位
            return -1
        if rank == 21 and offset == -1:
            # 雀士1掉无可掉
            return 21
        if rank == 53 and offset == 1:
            # 升上魂天！
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
            return '查无此人，请检查雀魂牌谱屋数字ID，不是雀魂好友ID'
        s1 = '{}{}'.format(ZONE_TAG.get(self.get_account_zone(rank_info['pid'])), rank_info['nickname'])
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

    def get_start_of_week(self, week=0):
        return int((datetime.now() + timedelta(days=-datetime.now().weekday(), weeks=week)).replace(hour=0, minute=0, second=0).timestamp())

    async def get_weekly_summary(self, week_offset=-1, bot_info={}):
        news = {}
        madata = loadjson(MAJIANG)
        memberdata = loadjson(MEMBER)
        start_of_week = self.get_start_of_week(week_offset)
        end_of_week = start_of_week + 86400 * 7 - 1
        logger.info('雀魂雷达开始生成周报')
        # 获取所有人上周的所有比赛
        all_record = []
        all_uuid = []
        for pid in madata['majsoul']['players']:
            for m in ['3', '4']:
                last_end = madata['majsoul']['players'][pid][m]['last_end']
                records = None
                try:
                    # logger.info(f'{pid} {m} 请求雀魂玩家上周所有比赛')
                    url = PPW_RECORDS[m].format(pid, end_of_week, start_of_week)
                    records = requests.get(url).json()
                except Exception as e:
                    logger.warning(e)
                    continue
                if not records:
                    # logger.info(f'{pid} {m} 没有发现任何比赛')
                    continue
                for record in records:
                    # 去重，防止群友排到同一桌重复计算
                    if record['uuid'] not in all_uuid:
                        all_record.append(record)
                        all_uuid.append(record['uuid'])
        for group in madata['subscribe_groups']:
            messages = []
            messages.append({
                'user_id': None,
                'message': '雀魂周报来了！({} - {})'.format(
                    datetime.fromtimestamp(start_of_week).strftime('%m/%d'),
                    datetime.fromtimestamp(end_of_week).strftime('%m/%d'),
                )
            })
            players_in_group = []
            for s in madata['majsoul']['subscribers']:
                if s in memberdata[group]:
                    players_in_group.append(madata['majsoul']['subscribers'][s])
            summary = []
            group_total_matches = 0
            group_total_delta = 0
            for player in players_in_group:
                player_total_matches = 0
                player_total_delta = 0
                for record in all_record:
                    for rp in record['players']:
                        if rp['accountId'] == int(player):
                            player_total_matches += 1
                            group_total_matches += 1
                            player_total_delta += rp['gradingScore']
                            group_total_delta += rp['gradingScore']
                            break
                summary.append({
                    'player': player,
                    'total_matches': player_total_matches,
                    'total_delta': player_total_delta,
                    'average_delta': player_total_delta / player_total_matches if player_total_matches > 0 else 0,
                })
            summary.sort(key=lambda x:-x['total_matches'])
            max_matches = summary[0]
            total_summary = '\n'.join([
                '{}{} 打了{}局，{}{}'.format(
                    ZONE_TAG.get(self.get_account_zone(player['player'])),
                    madata['majsoul']['players'][player['player']]['nickname'],
                    player['total_matches'],
                    '+' if player['total_delta'] > 0 else '±' if player['total_delta'] == 0 else '',
                    player['total_delta']
                ) for player in summary
            ])
            messages.append({
                'user_id': None,
                'message': total_summary
            })
            to_delete = []
            for player in summary:
                if player['total_matches'] == 0:
                    to_delete.append(player)
            for player in to_delete:
                summary.remove(player)
            if len(summary):
                summary.sort(key=lambda x:-x['total_delta'])
                max_delta = summary[0]
                min_delta = summary[-1]
                summary.sort(key=lambda x:-x['average_delta'])
                max_average_delta = summary[0]
                min_average_delta = summary[-1]
                if group_total_matches > 0:
                    group_average_delta = group_total_delta / group_total_matches
                    messages.append({
                        'user_id': None,
                        'message': '群友们一共打了{}局，{}{}，局均{}{:.2f}'.format(
                            group_total_matches,
                            '+' if group_total_delta > 0 else '±' if group_total_delta == 0 else '',
                            group_total_delta,
                            '+' if group_average_delta > 0 else '±' if group_average_delta == 0 else '',
                            group_average_delta,
                        )
                    })
                if max_matches['total_matches'] > 0:
                    messages.append({
                        'user_id': madata['majsoul']['players'][max_matches['player']]['subscribers'][0],
                        'message': '打得最多：{}{} {}局'.format(
                            ZONE_TAG.get(self.get_account_zone(max_matches['player'])),
                            madata['majsoul']['players'][max_matches['player']]['nickname'],
                            max_matches['total_matches']
                        )
                    })
                if max_delta['total_delta'] > 0:
                    messages.append({
                        'user_id': madata['majsoul']['players'][max_delta['player']]['subscribers'][0],
                        'message': '上分最多：{}{} +{}'.format(
                            ZONE_TAG.get(self.get_account_zone(max_delta['player'])),
                            madata['majsoul']['players'][max_delta['player']]['nickname'],
                            max_delta['total_delta']
                        )
                    })
                if max_average_delta['average_delta'] > 0:
                    messages.append({
                        'user_id': madata['majsoul']['players'][max_average_delta['player']]['subscribers'][0],
                        'message': '局均最高：{}{} +{:.2f}'.format(
                            ZONE_TAG.get(self.get_account_zone(max_average_delta['player'])),
                            madata['majsoul']['players'][max_average_delta['player']]['nickname'],
                            max_average_delta['average_delta']
                        )
                    })
                if min_delta['total_delta'] < 0:
                    messages.append({
                        'user_id': madata['majsoul']['players'][min_delta['player']]['subscribers'][0],
                        'message': '掉分最多：{}{} {}'.format(
                            ZONE_TAG.get(self.get_account_zone(min_delta['player'])),
                            madata['majsoul']['players'][min_delta['player']]['nickname'],
                            min_delta['total_delta']
                        )
                    })
                if min_average_delta['average_delta'] < 0:
                    messages.append({
                        'user_id': madata['majsoul']['players'][min_average_delta['player']]['subscribers'][0],
                        'message': '局均最低：{}{} {:.2f}'.format(
                            ZONE_TAG.get(self.get_account_zone(min_average_delta['player'])),
                            madata['majsoul']['players'][min_average_delta['player']]['nickname'],
                            min_average_delta['average_delta']
                        )
                    })
            else:
                for player in players_in_group:
                    messages.append({
                        'user_id': madata['majsoul']['players'][player]['subscribers'][0],
                        'message': '我们是冠军！'
                    })
            news[group] = messages
        return news

    async def get_news_async(self, bot_info={}):
        '''
        返回最新消息
        '''
        news = {}
        news_cnt = 0
        madata = loadjson(MAJIANG)
        memberdata = loadjson(MEMBER)
        now = int(datetime.now().timestamp())
        logger.info('雀魂雷达开始扫描')
        records = None
        # 获取所有人的数据
        for pid in madata['majsoul']['players']:
            for m in ['3', '4']:
                msg = ''
                last_end = madata['majsoul']['players'][pid][m]['last_end']
                total_delta = 0
                records = None
                try:
                    # logger.info(f'{pid} {m} 请求雀魂玩家最近比赛')
                    end_of_today = int(datetime.now().replace(hour=23, minute=59, second=59).timestamp())
                    url = PPW_RECORDS[m].format(pid, end_of_today, last_end)
                    records = requests.get(url).json()
                except Exception as e:
                    logger.warning(e)
                    logger.info(url)
                    continue
                if not records:
                    # logger.info(f'{pid} {m} '没有发现任何比赛')
                    continue
                if records[0] and records[0].get('startTime') > last_end:
                    logger.info(f'{pid} {m} 发现最近比赛更新！ {len(records)}')
                else:
                    # 实际上请求的API就是从上次比赛结束后更新的比赛
                    # 返回的结果如果存在records[0]，那么必定是更新的比赛
                    logger.info(f'{pid} {m} 没有发现最近比赛更新')
                    continue
                if records[0].get('endTime'):
                    madata['majsoul']['players'][pid][m]['last_end'] = records[0].get('endTime')
                len_records = len(records)
                while(len(records)):
                    tosend = []
                    match = records.pop(-1)
                    # madata['majsoul']['players'][pid][m]['last_end'] = match.get('endTime')
                    start_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(match.get('startTime')))
                    duration = match.get('endTime') - match.get('startTime')
                    mode = GAME_MODE.get(match.get('modeId'), '未知')
                    for mp in match.get('players'):
                        if int(mp['accountId']) == int(pid):
                            subscriber = '{}{}'.format(ZONE_TAG.get(self.get_account_zone(mp['accountId'])), mp['nickname'])
                            madata['majsoul']['players'][pid]['nickname'] = mp['nickname']

                    # 实时计算段位变动
                    stats = requests.get(PPW_STATS[m].format(pid, START, match.get('startTime'), match.get('startTime') // 60)).json()
                    pre_rank = stats['level']['id'] // 100 % 10 * 10 + stats['level']['id'] % 10
                    pre_score = stats['level']['score']
                    cur_rank = pre_rank
                    offset = stats['level']['delta']
                    cur_score = pre_score + offset
                    total_delta += offset
                    if RANK_SCORE.get(cur_rank):
                        if cur_score >= RANK_SCORE[cur_rank]: # 升段
                            cur_rank = self.get_next_rank(cur_rank)
                            cur_score = RANK_SCORE[cur_rank] // 2
                        if cur_score < 0: # 掉段
                            if cur_rank == 21:
                                cur_score = 0
                            else:
                                cur_rank = self.get_next_rank(cur_rank, -1)
                                cur_score = RANK_SCORE[cur_rank] // 2
                    madata['majsoul']['players'][pid][m]['rank'] = cur_rank
                    madata['majsoul']['players'][pid][m]['score'] = cur_score

                    rank_change = ''
                    if cur_rank != pre_rank:
                        if cur_rank:
                            if pre_rank:
                                word = '升' if cur_rank > pre_rank else '掉'
                                rank_change = '，直接进行一个段的{}'.format(word)
                            else:
                                pass
                                # msg += '，{}段位达到了{}{}'.format(
                                #     '零一二三四'[int(m)] + '麻',
                                #     PLAYER_RANK[cur_rank // 10],
                                #     cur_rank % 10 or ''
                                # )
                        else:
                            pass
                    # tosend.append('雀魂雷达动叻！')
                    # tosend.append('{} 打了一局 [{}]'.format(subscriber, mode))
                    # tosend.append('开始时间: {}'.format(start_time))
                    # tosend.append('持续时间: {}分{}秒'.format(duration // 60, duration % 60))
                    players = []
                    wind = 0
                    playernum = len(match.get('players'))
                    for mp in match.get('players'):
                        wind += 1
                        score = mp['score'] + playernum - wind
                        players.append((mp['accountId'], score))
                    players.sort(key=lambda i: i[1], reverse=True)
                    for mp in players:
                        if int(mp[0]) == int(pid):
                            rank_in_game = '{}位'.format(players.index(mp) + 1)
                            score = str(mp[1] // 10 * 10)
                            negative = '，飞了' if mp[1] < 0 else ''
                            # wind = '？东南西北'[playernum - mp[1] % 10]
                            # mp_result = [rank_in_game, wind, mp[0], score]
                            # if mp[1] < 0:
                                # mp_result.append('飞了！')
                            # tosend.append(' '.join(mp_result))
                            break
                    if len_records == 1:
                        msg = '{} {}打了一局[{}]，{}{}，{}，{}{}{}，现在是{}麻{}{}({}/{})'.format(
                            datetime.fromtimestamp(match['endTime']).strftime('[%Y-%m-%d %H:%M:%S]'),
                            subscriber,
                            mode,
                            score,
                            negative,
                            rank_in_game,
                            '+' if offset > 0 else '±' if offset == 0 else '',
                            offset,
                            rank_change,
                            '三四'[int(m) - 3],
                            PLAYER_RANK[cur_rank // 10],
                            cur_rank % 10 or '',
                            cur_score,
                            RANK_SCORE[cur_rank],
                        )
                    else:
                        msg += '{} {}打了一局[{}]，{}{}，{}，{}{}{}\n'.format(
                            datetime.fromtimestamp(match['endTime']).strftime('[%Y-%m-%d %H:%M:%S]'),
                            subscriber,
                            mode,
                            score,
                            negative,
                            rank_in_game,
                            '+' if offset > 0 else '±' if offset == 0 else '',
                            offset,
                            rank_change,
                        )
                        if not len(records):
                            msg += '{} {} {}{}，现在是{}麻{}{}({}/{})'.format(
                                datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'),
                                subscriber,
                                '+' if total_delta > 0 else '±' if total_delta == 0 else '',
                                total_delta,
                                '三四'[int(m) - 3],
                                PLAYER_RANK[cur_rank // 10],
                                cur_rank % 10 or '',
                                cur_score,
                                RANK_SCORE[cur_rank],
                            )
                news_cnt += 1
                for subscriber in madata['majsoul']['players'][pid]['subscribers']:
                    if subscriber in news:
                        news[subscriber].append(msg)
                    else:
                        news[subscriber] = [msg]

        dumpjson(madata, MAJIANG)

        logger.info(f'雀魂雷达扫描到了{news_cnt}个新事件')

        # for msg in news:
        #     msg['target_groups'] = []
        #     for u in msg['user']:
        #         for g in memberdata:
        #             if u in memberdata[g] and g not in msg['target_groups']:
        #                 msg['target_groups'].append(g)

        return news