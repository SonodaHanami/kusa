import json
import os
import random
import pygtrie
import re
import requests
import sys
from datetime import datetime, timedelta
from apscheduler.triggers.cron import CronTrigger

from . import whois
from .utils import *

CONFIG = load_config()
APIKEY = CONFIG['STEAM_APIKEY']
BOT = CONFIG['BOT']
ATBOT = f'[CQ:at,qq={BOT}]'
UNKNOWN = None
IDK = '我不知道'
MEMBER = os.path.expanduser('~/.kusa/member.json')
STEAM  = os.path.expanduser('~/.kusa/steam.json')

class Steam:
    Passive = False
    Active = True
    Request = False

    def __init__(self, **kwargs):
        self.api = kwargs['bot_api']

    async def execute_async(self, message):
        msg = message['raw_message'].strip()
        group = str(message.get('group_id', ''))
        user = str(message.get('user_id', ''))
        if not group:
            return None
        atbot = False
        if msg.startswith(ATBOT):
            msg = msg[len(ATBOT):].strip()
            atbot = True

        prm = re.match('绑定steam (\d+)', msg, re.I)
        if prm:
            try:
                id3 = int(prm[1])
                id64 = id3 + 76561197960265728
                steamdata = loadjson(STEAM)
                steamdata[user] = {
                    "steam_id_short": id3,
                    "steam_id_long": id64,
                    "last_DOTA2_match_ID": 0,
                    "last_change": 0,
                    "gameextrainfo": "",
                }
                dumpjson(steamdata, STEAM)
                return '绑定成功'
            except:
                return '使用方法：\n绑定Steam Steam好友代码（9位）（也可能是8位或10位）'

        if msg.lower() == '解除绑定steam':
            steamdata = loadjson(STEAM)
            if steamdata.get(user):
                del steamdata[user]
                dumpjson(steamdata, STEAM)
                return '解除绑定成功'
            else:
                return '没有找到你的绑定记录'

    def jobs(self):
        trigger = CronTrigger(minute='*', second='30')
        job = (trigger, self.send_news_async)
        return (job,)

    async def send_news_async(self):
        steamdata = loadjson(STEAM)
        groups = steamdata.get('subscribe_groups')
        if not groups:
            return None
        news = await self.get_news_async()
        sends = []
        for msg in news:
            for g in groups:
                if str(g) in msg['target_groups']:
                    sends.append({
                        "message_type": "group",
                        "group_id": g,
                        "message": msg['message']
                    })
        return sends

    async def get_news_async(self):
        '''
        返回最新消息
        '''
        news = []
        memberdata = loadjson(MEMBER)
        steamdata = loadjson(STEAM)
        players = self.get_players()
        matches = {}
        replys = []
        status_changed = False
        sids = ','.join(str(p) for p in players.keys())
        r = requests.get(f'http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key={APIKEY}&steamids={sids}')
        j = json.loads(r.content)
        for p in j['response']['players']:
            sid = int(p['steamid'])
            for q in players[sid]:
                cur_game = p.get('gameextrainfo', '')
                pre_game = steamdata[q]['gameextrainfo']
                pname    = p['personaname']

                # 游戏状态更新
                if cur_game != pre_game:
                    status_changed = True
                    now = int(datetime.now().timestamp())
                    minutes = (now - steamdata[q]['last_change']) // 60
                    if cur_game:
                        if pre_game:
                            mt = f'{pname}玩了{minutes}分钟{pre_game}后，玩起了{cur_game}'
                        else:
                            mt = f'{pname}启动了{cur_game}'
                        if datetime.now().hour <= 6:
                            mt += '\n你他娘的不用睡觉吗？'
                        if datetime.now().weekday() < 5 and datetime.now().hour in range(8, 18):
                            mt += '\n见鬼，这群人都不用上班的吗'
                        news.append({
                            'message': mt,
                            'user'   : [q]
                        })
                    else:
                        news.append({
                            'message': f'{pname}退出了{pre_game}，本次游戏时长{minutes}分钟',
                            'user'   : [q]
                        })
                    steamdata[q]['gameextrainfo'] = cur_game
                    steamdata[q]['last_change'] = now

        if status_changed:
            dumpjson(steamdata, STEAM)

        for msg in news:
            msg['target_groups'] = []
            for u in msg['user']:
                for g in memberdata:
                    if u in memberdata[g] and g not in msg['target_groups']:
                        msg['target_groups'].append(g)

        return news


    def get_players(self):
        memberdata = loadjson(MEMBER)
        steamdata  = loadjson(STEAM)
        players = {}
        for g in memberdata:
            for qq in memberdata.get(g):
                steam_info = steamdata.get(qq)
                if steam_info:
                    sid = steam_info.get('steam_id_long')
                    if sid:
                        if sid not in players:
                            players[sid] = [qq]
                        else:
                            players[sid].append(qq)
        return players
