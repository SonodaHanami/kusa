class Kusa:
    def __init__(self):
        pass

    async def execute_async(self, message):
        msg = message['raw_message'].strip()
        group = str(message.get('group_id', ''))
        user = str(message.get('user_id', ''))

        return '草'