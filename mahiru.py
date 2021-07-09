import json
import os
import random
import re
from datetime import datetime, timedelta
from apscheduler.triggers.cron import CronTrigger
from .utils import *

CONFIG = load_config()
ADMIN = CONFIG['ADMIN']
MAHIRU = os.path.expanduser('~/.kusa/mahiru.json')

DEFAULT_DATA = {
    'jobs': [],
}

class Mahiru:
    # 不也挺好吗.jpg
    Passive = False
    Active = True
    Request = False

    def __init__(self, **kwargs):
        print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), '初始化Mahiru')

        self.api = kwargs['bot_api']
        self.MINUTE = random.randint(10, 30)
        if not os.path.exists(MAHIRU):
            dumpjson(DEFAULT_DATA, MAHIRU)

    async def execute_async(self, message):
        msg = message['raw_message'].strip()
        if re.match('订阅闹钟(.+)', msg):
            # TODO
            pass
        return None

    def jobs(self):
        trigger = CronTrigger(minute='*')
        job = (trigger, self.mahiru)
        return (job,)

    async def mahiru(self):
        mahirudata = loadjson(MAHIRU)
        dtstr = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        for j in mahirudata['jobs']:
            if self.check(j['condition']):
                msg = re.sub('\$DATETIME', dtstr, j['message'])
                if j['type'] == 'private':
                    await self.api.send_private_msg(
                        user_id=j['target'],
                        message=msg,
                    )
                if j['type'] == 'group':
                    await self.api.send_group_msg(
                        group_id=j['target'],
                        message=msg,
                    )

    def check(self, condition):
        now = datetime.now()
        h = now.hour
        m = now.minute
        hm = h * 100 + m

        return hm in condition