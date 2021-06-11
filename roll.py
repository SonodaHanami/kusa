import random
import re
from random import randint as ri

DEFAULT_PLANE = 6
MAX_DICE = 10
MAX_PLANE = 1024

class Roll:
    def __init__(self, **kwargs):
        self.api = kwargs['bot_api']
        self.plane = DEFAULT_PLANE

    async def execute_async(self, message):
        msg = message['raw_message']
        group = str(message.get("group_id", ''))
        user = str(message.get("user_id", 0))
        replys = []

        prm = re.match('([/!\.]?roll|[/!\.]r)(.*)', msg)
        if prm:
            try:
                msg = prm[2].strip()
                if not msg:
                    return '{}'.format(ri(1, 100))
                prm = re.findall('(\d+)?d(\d+)?([\+\-]\d+)?', msg)
                for p in prm:
                    dice =  int(p[0]) if p[0] else 1
                    plane = int(p[1]) if p[1] else self.plane
                    delta = int(p[2]) if p[2] else 0
                    if plane <= 0:
                        return '¿'
                    if plane > MAX_PLANE:
                        return '这么多面，建议玩球'
                    if dice > MAX_DICE:
                        return '唔得，骰子不够叻'
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
                prm = re.match('([\+\-]?\d+)', msg)
                if prm:
                    n = int(prm[1])
                    if n <= 0:
                        return '{}'.format(ri(n, 0))
                    return '{}'.format(ri(1, n))
            except Exception as e:
                return 'Roll error: {}'.format(e)

        prm = re.match('([/!\.]set)(.*)', msg)
        if prm:
            msg = prm[2].strip()
            if not msg:
                self.plane = DEFAULT_PLANE
                return '默认面数现在是{}'.format(self.plane)
            prm = re.match('([\+\-]?\d+)', msg)
            if prm:
                p = int(prm[1])
                if p <= 0:
                    return '¿'
                if p > MAX_PLANE:
                    return '这么多面，建议玩球'
                self.plane = p
                return '默认面数现在是{}'.format(self.plane)