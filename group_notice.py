from .utils import *

logger = get_logger('kusa')

class GroupNotice:
    def __init__(self, **kwargs):
        logger.info('初始化Rogue')

        # group_id : last_vurl
        self.api = kwargs['bot_api']
        self.whois = kwargs['whois']

    async def execute_async(self, message):
        return None

    async def handle_notice_async(self, ev):
        notice_type = ev.get('notice_type')
        if notice_type == 'group_increase':
            reply = '[CQ:at,qq={}] 欢迎新人！'.format(ev['user_id'])
            init_result = await self.whois.init_group_member(str(ev['group_id']))
            await self.api.send_group_msg(
                group_id=ev['group_id'],
                message=reply,
            )
        if notice_type == 'group_decrease':
            info = await self.api.get_stranger_info(user_id=ev['user_id'])
            reply = '{}({})退群了，白白喵，白白喵~'.format(
                    info['nickname'],
                    ev['user_id'],
                )
            init_result = await self.whois.init_group_member(str(ev['group_id']))
            await self.api.send_group_msg(
                group_id=ev['group_id'],
                message=reply,
            )