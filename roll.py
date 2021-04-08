import random
import re
from random import randint as ri

DEFAULT_PLANE = 6
MAX_DICE = 10
MAX_PLANE = 20

class Roll:
    def __init__(self, **kwargs):
        self.api = kwargs['bot_api']

    async def execute_async(self, message):
        msg = message['raw_message']
        group = str(message.get("group_id", ''))
        user = str(message.get("user_id", 0))
        replys = []

        if msg.startswith('/'):
            msg = msg[1:].strip()

        if msg.startswith('roll'):
            msg = msg[4:].strip()
            if not msg:
                return '{}'.format(ri(1, 100))
            try:
                prm = re.findall('(\d+)?d(\d+)?([\+\-]\d+)?', msg)
                for p in prm:
                    dice =  int(p[0]) if p[0] else 1
                    plane = int(p[1]) if p[1] else DEFAULT_PLANE
                    delta = int(p[2]) if p[2] else 0
                    if plane <= 0:
                        return '¿'
                    if plane > MAX_PLANE:
                        return '这么多面，建议玩球'
                    for i in range(dice):
                        replys.append('{}'.format(ri(1, plane) + delta))
                if replys:
                    if len(replys) > MAX_DICE:
                        return '唔得，骰子不够叻'
                    return ' '.join(replys)

                prm = re.match('([\+\-]?\d+) +([\+\-]?\d+)', msg)
                if prm:
                    l, r = min(int(prm[1]), int(prm[2])), max(int(prm[1]), int(prm[2]))
                    return '{}'.format(ri(l, r))
                prm = re.match('(\d+)', msg)
                if prm:
                    if int(prm[1]) <= 0:
                        return 0
                    return '{}'.format(ri(1, int(prm[1])))
            except Exception as e:
                return 'Roll error: {}'.format(e)