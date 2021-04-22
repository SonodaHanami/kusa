import json
import os
import random
import re
import requests
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
from random import randint as ri
from .utils import *

CONFIG = load_config()
ADMIN = CONFIG['ADMIN']

# https://api.lolicon.app/#/setu
APIKEY = CONFIG['SETU_APIKEY']
SOURCE_LOLICON_APP = 'https://api.lolicon.app/setu/'

SETU = os.path.expanduser('~/.kusa/setu.json')
JIESE = os.path.expanduser('~/.kusa/jiese.json')
MAX_TIME = 5
JIESE_LIMIT = 3

class Setu:
    def __init__(self, **kwargs):
        self.api = kwargs['bot_api']

    async def execute_async(self, message):
        msg = message['raw_message']
        group = str(message.get("group_id", ''))
        user = str(message.get("user_id", 0))
        if msg == '戒色':
            jiesedata = loadjson(JIESE)
            jiesedata[group] = []
            dumpjson(jiesedata, JIESE)
            return f'好，本群已戒色，累计{JIESE_LIMIT}人发送“我要色图”可解除戒色'
        if msg == '我要色图':
            jiesedata = loadjson(JIESE)
            jiesedata[group].append(user)
            jiesedata[group] = list(set(jiesedata[group]))
            cnt = len(jiesedata[group])
            if cnt >= JIESE_LIMIT:
                del jiesedata[group]
                reply = f'好，已收集到{cnt}份签名，本群已解除戒色'
            else:
                reply = f'好，已收集到{cnt}份签名，还需{JIESE_LIMIT - cnt}份可解除戒色'
            dumpjson(jiesedata, JIESE)
            return reply
        if msg[0:2] in ('色图', '涩图'):
            jiesedata = loadjson(JIESE)
            setudata = loadjson(SETU)
            time = setudata.get(user, [0, 0])[0]
            prev = setudata.get(user, [0, 0])[1]

            cnt = len(jiesedata.get(group, [0, 0, 0]))
            if cnt < JIESE_LIMIT:
                return f'[CQ:at,qq={user}] 本群已戒色，累计{JIESE_LIMIT}人发送“我要色图”可解除戒色（{cnt}/{JIESE_LIMIT}）'

            if time >= MAX_TIME:
                return f'[CQ:at,qq={user}] 你今天冲太多了，明天再来吧'

            now = int(datetime.now().timestamp())
            if now - prev < 60:
                return f'[CQ:at,qq={user}] 你冲得太快了，请稍后重试'

            keyword = msg[2:].strip()
            if message["message_type"] == "group":
                await self.api.send_group_msg(
                    group_id=message['group_id'],
                    message=f'正在搜索',
                )
            elif message["message_type"] == "private":
                pass

            url = f'{SOURCE_LOLICON_APP}?apikey={APIKEY}&r18=0&num=1&size1200=false'
            if keyword:
                url += f'&keyword={keyword}'
            r = requests.get(url)
            data = json.loads(r.content)
            code = data['code']
            code_dict = {
                -1: '内部错误，请向 i@loli.best 反馈',
                0: '成功',
                401: 'APIKEY 不存在或被封禁',
                403: '由于不规范的操作而被拒绝调用',
                404: '找不到符合关键字的色图',
                429: '达到调用额度限制'
            }
            if code != 0:
                if code == 404:
                    return f'没有找到关键字{keyword}的涩图'
                errmsg = code_dict.get(code, '')
                return f'出错了！\n{errmsg}\n总之就是没有色图！'
            data = data['data'][0]
            pid = f"pid：{data['pid']} p{data['p']}"
            title = f"标题：{data['title']}"
            author = f"作者：{data['author']}"
            img_url = data['url']

            # 给我也来一份
            setu_path = os.path.expanduser("~/.kusa/setu/")
            file_path = os.path.join(setu_path, os.path.basename(img_url))
            if not os.path.exists(file_path):
                with open(os.path.join(setu_path, f"{data['pid']}_p{data['p']}.json"), 'w') as f:
                    json.dump(json.loads(r.content), f, indent=4, ensure_ascii=False)
                r = requests.get(img_url)
                with open(file_path, 'wb') as f:
                    f.write(r.content)

            setudata[user] = [time + 1, now]
            dumpjson(setudata, SETU)

            return f'{pid}\n{title}\n{author}\n[CQ:image,file=file:///{file_path},cache=1]'


    def jobs(self):
        trigger = CronTrigger(hour='5')
        job = (trigger, self.reset_setudata)
        return (job,)

    async def reset_setudata(self):
        default_data = {
            ADMIN: [-999, 0]
        }
        dumpjson(default_data, SETU)
