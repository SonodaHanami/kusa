import json
import os
import random
import re
from datetime import datetime
from functools import reduce
from random import randint as ri

from .utils import *
from . import (
    bilibili, github, mahiru, majiang, roll,
    setu, whois,
)


CONFIG = load_config()
ADMIN = CONFIG['ADMIN']
KUSA_JPG = '[CQ:image,file=b7e3ba3500b150db483fc9b7f69014cb.image]' # 草.jpg
PREVMSG = os.path.expanduser('~/.kusa/prevmsg.json')

MAX_MESSAGE_NUM = 5
MIN_TIME_TO_REPEAT = 2
MAX_TIME_TO_REPEAT = 4
PASS_CHAR = r'''
1234567890
abcdefghijklmnopqrstuvwxyz
ABCDEFGHIJKLMNOPQRSTUVWXYZ
 `~!@#$%^&*()-=_+\|[]{}'";:,./<>?
，。、（）【】！？“”：；
的地得了是哇哪嘛吗啊啦呀吧哦呢呐哈着过
'''


class Kusa:
    Passive = True
    Active = True
    Request = False

    def __init__(self, **kwargs):
        print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), '初始化kusa，草！')

        self.api = kwargs['bot_api']
        self.whois = whois.Whois(**kwargs)
        kwargs.update({'whois': self.whois})

        self.kusa_modules = [
            bilibili.Bangumi(**kwargs),
            github.Github(**kwargs),
            mahiru.Mahiru(**kwargs),
            majiang.Majiang(**kwargs),
            roll.Roll(**kwargs),
            setu.Setu(**kwargs),
            self.whois,
        ]

        self.joker_enabled = []

        print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), '初始化kusa完成！')

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

        if await self.admin(message):
            return None

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


    async def admin(self, message):
        msg = message['raw_message'].strip().lower()
        group = str(message.get('group_id', ''))
        user = str(message.get('user_id', ''))

        if user != ADMIN and message['message_type'] == 'group' and message['sender']['role'] == 'member':
            return None
        if msg.startswith('!') or msg.startswith('！'):
            msg = msg[1:]
            reply = ''
            if msg == 'lssv':
                reply = ', '.join([type(k).__name__ for k in self.kusa_modules])
            if msg.startswith('joker'):
                msg = msg[5:].strip()
                if msg == '':
                    reply = 'joker: {}'.format('active' if group in self.joker_enabled else 'inactive')
                elif msg == 'on':
                    if group not in self.joker_enabled:
                        self.joker_enabled.append(group)
                        reply = 'joker ON!'
                elif msg == 'off':
                    if group in self.joker_enabled:
                        self.joker_enabled.remove(group)
                        reply = 'joker OFF!'

            if reply:
                await self.api.send_group_msg(
                    group_id=group,
                    message=reply
                )
                return True


    def joker(self, message, replys):
        msg = message['raw_message'].strip().lower()
        group = str(message.get('group_id', ''))
        user = str(message.get('user_id', ''))
        nickname = message['sender'].get('card', '') or message['sender'].get('nickname', '')

        if group not in self.joker_enabled:
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
        prm = re.search('(.)(.+?)还是\\1(.+?)[？?]', msg)
        if prm:
            r = ri(1, 100)
            if r <= 45:
                replys.append('{}{}！'.format(prm[1], prm[2]))
            elif r <= 90:
                replys.append('{}{}！'.format(prm[1], prm[3]))
            else:
                replys.append('都不{}！'.format(prm[1]))
        else:
            prm = re.search('(.+?)还是(.+?)[？?]', msg)
            if prm:
                r = ri(1, 2)
                replys.append('{}！'.format(prm[r]))

        if ri(1, 80) == 1 and len(msg) > 1 and '[CQ:' not in msg:
            if ri(1, 2) == 1:
                i = ri(0, len(msg) - 2)
                if msg[i] not in PASS_CHAR and msg[i+1] not in PASS_CHAR:
                    replys.append(f'我直接进行一个{msg[i]}的{msg[i+1]}')
            else:
                i = ri(1, len(msg) - 1)
                if msg[i] not in PASS_CHAR and msg[i-1] not in PASS_CHAR:
                    replys.append(f'我直接进行一个{msg[i]}的{msg[i-1]}')

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

