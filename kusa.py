import json
import os
from aiocqhttp.api import Api
from random import randint as ri

from .util import *
from . import whois


CONFIG = load_config()
KUSA_JPG = '[CQ:image,file=b7e3ba3500b150db483fc9b7f69014cb.image]' # 草.jpg
PREVMSG = os.path.expanduser("~/.kusa/prevmsg.json")

MAX_MESSAGE_NUM = 5
MIN_TIME_TO_REPEAT = 2
MAX_TIME_TO_REPEAT = 4


class Kusa:
    Passive = True
    Active = False
    Request = False

    def __init__(self, bot_api: Api, **kwargs):
        self.api = bot_api

        self.whois = whois.Whois()

        self.kusa_modules = [
            self.whois,
        ]

    def match(self, msg):
        return 1

    async def execute_async(self, func_num, message):
        msg = message['raw_message'].strip()
        group = str(message.get('group_id', ''))
        user = str(message.get('user_id', ''))
        nickname = message["sender"].get("nickname", "")

        replys = []

        ##############################
        #   both private and group   #
        ##############################

        ''' 草 '''
        if msg.startswith('草'):
            if ri(1, 4) == 1:
                replys.append('草')
            elif ri(1, 9) == 1:
                replys.append(KUSA_JPG)

        if KUSA_JPG in msg and ri(1, 3) == 1:
            replys.append(KUSA_JPG)

        if message['message_type'] == 'private':
            return '\n'.join(replys) if replys else None

        ##############################    
        #   group only               #
        ##############################

        for k in self.kusa_modules:
            reply = await k.execute_async(message)
            if reply:
                replys.append(reply)

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


        return '\n'.join(replys) if replys else None