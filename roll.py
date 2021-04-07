import random
import re
from random import randint as ri

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
                prm = re.findall('(\d+)d(\d+)', msg)
                for p in prm:
                    for i in range(int(p[0])):
                        replys.append('{}'.format(ri(1, int(p[1]))))
                if replys:
                    return ' '.join(replys)
                prm = re.match('(\d+) +(\d+)', msg)
                if prm:
                    return '{}'.format(ri(int(prm[1]), int(prm[2])))
                prm = re.match('(\d+)', msg)
                if prm:
                    return '{}'.format(ri(1, int(prm[1])))
            except Exception as e:
                return 'Roll error: {}'.format(e)