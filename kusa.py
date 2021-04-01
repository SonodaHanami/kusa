from aiocqhttp.api import Api

class Kusa:
    Passive = True
    Active = False
    Request = False

    def __init__(self, bot_api: Api, **kwargs):
        self.api = bot_api

    def match(self, msg):
        return 1

    async def execute_async(self, func_num, message):
        msg = message['raw_message'].strip()
        group = str(message.get('group_id', ''))
        user = str(message.get('user_id', ''))

        replys = []


        return '\n'.join(replys) if replys else None