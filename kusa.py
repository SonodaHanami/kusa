import json
import os
import random
import re
from functools import reduce
from random import randint as ri

from .utils import *
from . import (
    bilibili, github, roll, setu, steam,
    whois,
)


CONFIG = load_config()
ADMIN = CONFIG['ADMIN']
KUSA_JPG = '[CQ:image,file=b7e3ba3500b150db483fc9b7f69014cb.image]' # 草.jpg
PREVMSG = os.path.expanduser("~/.kusa/prevmsg.json")

MAX_MESSAGE_NUM = 5
MIN_TIME_TO_REPEAT = 2
MAX_TIME_TO_REPEAT = 4


class Kusa:
    Passive = True
    Active = True
    Request = False

    def __init__(self, **kwargs):
        self.api = kwargs['bot_api']

        self.kusa_modules = [
            bilibili.Bangumi(**kwargs),
            github.Github(**kwargs),
            roll.Roll(**kwargs),
            setu.Setu(**kwargs),
            steam.Steam(**kwargs),
            whois.Whois(**kwargs),
        ]

        self.joker_disabled = []

    def jobs(self):
        jobs = []
        for k in self.kusa_modules:
            if hasattr(k, 'jobs'):
                jobs.append(k.jobs())
        return reduce(lambda x, y: x+y, jobs)

    def match(self, msg):
        return 1

    async def execute_async(self, func_num, message):
        msg = message['raw_message'].strip()
        group = str(message.get('group_id', ''))
        user = str(message.get('user_id', ''))

        replys = []

        ##############################
        #   both private and group   #
        ##############################

        self.admin(message)

        ''' 草 '''
        if msg.startswith('草'):
            if ri(1, 4) == 1:
                replys.append('草')
            elif ri(1, 9) == 1:
                replys.append(KUSA_JPG)
        if KUSA_JPG in msg and ri(1, 3) == 1:
            replys.append(KUSA_JPG)

        self.joker(message, replys)

        if message['message_type'] == 'private':
            return '\n'.join(replys) if replys else None

        ##############################    
        #   group only               #
        ##############################

        for k in self.kusa_modules:
            reply = await k.execute_async(message)
            if reply:
                replys.append(reply)

        await self.repeater(message, replys)

        return '\n'.join(replys) if replys else None


    def admin(self, message):
        msg = message['raw_message'].strip().lower()
        group = str(message.get('group_id', ''))
        user = str(message.get('user_id', ''))

        if user != ADMIN:
            return None
        if msg.startswith('!'):
            msg = msg[1:]
            if msg == 'lssv':
                return ', '.join([type(k).__name__ for k in self.kusa_modules])


    def joker(self, message, replys):
        msg = message['raw_message'].strip().lower()
        group = str(message.get('group_id', ''))
        user = str(message.get('user_id', ''))
        nickname = message["sender"].get("nickname", "")

        if msg == '!enable':
            if group in self.joker_disabled:
                self.joker_disabled.remove(group)
                replys.append('joker_enabled')
                return None
        if msg == '!disable':
            if group not in self.joker_disabled:
                self.joker_disabled.append(group)
                replys.append('joker_disabled')
                return None

        if group in self.joker_disabled:
            return None
        if msg.startswith('？') and ri(1, 3) == 1:
            replys.append('？')
        if msg.startswith('不是') and ri(1, 3) == 1:
            replys.append('不是，你为什么要说不是？')
        prm = re.search('(.+?)不\\1', msg)
        if '？' in msg and '是不是' in msg: # avoid Whois
            pass
        elif prm:
            replys.append(prm[1] if ri(1, 2) == 1 else f'不{prm[1]}')
        if '有没有' in msg:
            replys.append('有' if ri(1, 2) == 1 else '没有')

        if ri(1, 100) == 1 and '[CQ:' not in msg:
            replys.append(random.choice([
                '确实',
                '有一说一，确实',
                '就是啊',
                '就是说啊',
                '嗯嗯，是啊',
                '啊这',
                '……',
                '。。。',
            ]))


    async def repeater(self, message, replys):
        msg = message['raw_message'].strip()
        group = str(message.get('group_id', ''))

        ''' 复读 '''
        prevmsg = loadjson(PREVMSG)
        if group not in prevmsg:
            prevmsg[group] = []
        msg_list = [list(d.keys())[0] for d in prevmsg[group]]
        try:
            idx = msg_list.index(msg)
        except ValueError:
            idx = None
        if replys:
            if idx is not None:
                prevmsg[group].remove(prevmsg[group][idx])
        else:
            if idx is not None:
                prevmsg[group][idx][msg] += 1
                if prevmsg[group][idx][msg] >= ri(MIN_TIME_TO_REPEAT, MAX_TIME_TO_REPEAT):
                    await self.api.send_group_msg(group_id=group, message=msg)
                    prevmsg[group].remove(prevmsg[group][idx])
                else:
                    prevmsg[group].append(prevmsg[group].pop(idx))
            else:
                prevmsg[group].append({msg: 1})
        while len(prevmsg[group]) > MAX_MESSAGE_NUM:
            prevmsg[group].remove(prevmsg[group][0])
        dumpjson(prevmsg, PREVMSG)

