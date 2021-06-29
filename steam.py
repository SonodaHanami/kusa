import json
import os
import random
import re
import requests
import time
from datetime import datetime, timedelta
from apscheduler.triggers.cron import CronTrigger
from PIL import Image, ImageDraw, ImageFont

from . import whois
from .DOTA2_dicts import *
from .utils import *

CONFIG = load_config()
APIKEY = CONFIG['STEAM_APIKEY']
BOT = CONFIG['BOT']
ATBOT = f'[CQ:at,qq={BOT}]'
UNKNOWN = None
IDK = '我不知道'
MAX_ATTEMPTS = 5
MEMBER = os.path.expanduser('~/.kusa/member.json')
STEAM  = os.path.expanduser('~/.kusa/steam.json')
IMAGES = os.path.expanduser('~/.kusa/images/')
DOTA2_MATCHES = os.path.expanduser('~/.kusa/DOTA2_matches/')

PLAYER_SUMMARY = 'http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key={}&steamids={}'
LAST_MATCH = 'https://api.steampowered.com/IDOTA2Match_570/GetMatchHistory/v001/?key={}&account_id={}&matches_requested=1'
MATCH_DETAILS = 'https://api.steampowered.com/IDOTA2Match_570/GetMatchDetails/V001/?key={}&match_id={}'
OPENDOTA_REQUEST = 'https://api.opendota.com/api/request/{}'
OPENDOTA_MATCHES = 'https://api.opendota.com/api/matches/{}'
OPENDOTA_PLAYERS = 'https://api.opendota.com/api/players/{}'

class Steam:
    Passive = False
    Active = True
    Request = False

    def __init__(self, **kwargs):
        self.api = kwargs['bot_api']

        mkdir_if_not_exists(DOTA2_MATCHES)

        self.MINUTE = random.randint(0, 59)
        print('Steam初始化，MINUTE={}'.format(self.MINUTE))
        self.dota2 = Dota2()


    async def execute_async(self, message):
        msg = message['raw_message'].strip()
        group = str(message.get('group_id', ''))
        user = str(message.get('user_id', ''))
        if not group:
            return None
        atbot = False
        if msg.startswith(ATBOT):
            msg = msg[len(ATBOT):].strip()
            atbot = True

        if msg.lower() == '订阅steam':
            steamdata = loadjson(STEAM)
            if group in steamdata['subscribe_groups']:
                return '本群已订阅Steam'
            else:
                steamdata['subscribe_groups'].append(group)
                dumpjson(steamdata, STEAM)
                return '订阅Steam成功'

        if msg.lower() == '取消订阅steam':
            steamdata = loadjson(STEAM)
            if group in steamdata['subscribe_groups']:
                steamdata['subscribe_groups'].remove(group)
                dumpjson(steamdata, STEAM)
                return '取消订阅Steam成功'
            else:
                return '本群未订阅Steam'

        prm = re.match('(怎么)?绑定 *steam(.*)', msg, re.I)
        if prm:
            usage = '使用方法：\n绑定Steam Steam好友代码（8~10位）'
            success = '绑定{}成功'
            try:
                if prm[1]:
                    return usage
                id3 = int(prm[2])
                if id3 > 76561197960265728:
                    id3 -= 76561197960265728
                id64 = id3 + 76561197960265728
                id3 = str(id3)
                steamdata = loadjson(STEAM)
                # 之前已经绑定过
                if steamdata['subscribers'].get(user):
                    old_id3 = steamdata['subscribers'][user]
                    if old_id3 != id3:
                        steamdata['players'][old_id3]['subscribers'].remove(user)
                        if not steamdata['players'][old_id3]['subscribers']:
                            del steamdata['players'][old_id3]
                        success += f'\n已自动解除绑定{old_id3}'
                steamdata['subscribers'][user] = id3
                if steamdata['players'].get(id3):
                    steamdata['players'][id3]['subscribers'].append(user)
                    steamdata['players'][id3]['subscribers'] = list(set(steamdata['players'][id3]['subscribers']))
                else:
                    steamdata['players'][id3] = {
                        'steam_id64': id64,
                        'subscribers': [user],
                        'gameextrainfo': '',
                        'last_change': 0,
                        'last_DOTA2_action': 0,
                        'last_DOTA2_match_id': 0,
                        'DOTA2_rank_tier': 0,
                    }
                dumpjson(steamdata, STEAM)
                return success.format(id3)
            except:
                return usage

        if msg.lower() == '解除绑定steam':
            steamdata = loadjson(STEAM)
            if steamdata['subscribers'].get(user):
                id3 = steamdata['subscribers'][user]
                steamdata['players'][id3]['subscribers'].remove(user)
                if not steamdata['players'][id3]['subscribers']:
                    del steamdata['players'][id3]
                del steamdata['subscribers'][user]
                dumpjson(steamdata, STEAM)
                return '解除绑定成功'
            else:
                return '没有找到你的绑定记录'

        prm = re.match('(.+)在(干|做|搞|整)(嘛|啥|哈|什么)', msg)
        if prm:
            name = prm[1].strip()
            steamdata = loadjson(STEAM)
            memberdata = loadjson(MEMBER)
            if re.search('群友', name):
                is_solo = False
                players_in_group = []
                for qq, id3 in steamdata['subscribers'].items():
                    if qq in memberdata[group]:
                        players_in_group.append(steamdata['players'][id3]['steam_id64'])
                players_in_group = list(set(players_in_group))
                sids = ','.join(str(p) for p in players_in_group)
            else:
                is_solo = True
                wi = whois.Whois()
                obj = wi.object_explainer(group, user, name)
                name = obj['name'] or name
                steam_info = steamdata['players'].get(steamdata['subscribers'].get(obj['uid']))
                if steam_info:
                    sids = steam_info.get('steam_id64')
                    if not sids:
                        return IDK
                else: # steam_info is None
                    if obj['uid'] == UNKNOWN:
                        return f'我们群里有{name}吗？'
                    return f'{IDK}，因为{name}还没有绑定SteamID'
            replys = []
            j = requests.get(PLAYER_SUMMARY.format(APIKEY, sids)).json()
            for p in j['response']['players']:
                if p.get('gameextrainfo'):
                    replys.append(p['personaname'] + '正在玩' + p['gameextrainfo'])
                elif is_solo:
                    replys.append(p['personaname'] + '没在玩游戏')
            if replys:
                if len(replys) > 2:
                    replys.append('大家都有光明的未来！')
                return '\n'.join(replys)
            elif not is_solo:
                return '群友都没在玩游戏'
            return IDK

        prm = re.match('查询(.+)的天梯段位$', msg)
        if prm:
            await self.api.send_group_msg(
                    group_id=message['group_id'],
                    message=f'正在查询',
                )
            name = prm[1].strip()
            steamdata = loadjson(STEAM)
            memberdata = loadjson(MEMBER)
            if re.search('群友', name):
                is_solo = False
                players_in_group = []
                for qq, id3 in steamdata['subscribers'].items():
                    if qq in memberdata[group]:
                        players_in_group.append(id3)
                players_in_group = list(set(players_in_group))
            else:
                is_solo = True
                wi = whois.Whois()
                obj = wi.object_explainer(group, user, name)
                name = obj['name'] or name
                id3 = steamdata['subscribers'].get(obj['uid'])
                if not id3:
                    if obj['uid'] == UNKNOWN:
                        return f'我们群里有{name}吗？'
                    return f'查不了，{name}可能还没有绑定SteamID'
                players_in_group = [id3]
            ranks = []
            replys = []
            for id3 in players_in_group:
                name, rank = self.dota2.get_rank_tier(id3)
                if rank:
                    ranks.append((name, rank))
            if ranks:
                ranks = sorted(ranks, key=lambda i: i[1], reverse=True)
                for name, rank in ranks:
                    replys.append('{}现在是{}{}'.format(name, PLAYER_RANK[rank // 10], rank % 10 or ''))
                if len(replys) > 2:
                    replys.append('大家都有光明的未来！')
                return '\n'.join(replys)
            else:
                return '查不到哟'

        prm = re.match('查询(.+)的(常用英雄|英雄池)$', msg)
        if prm:
            name = prm[1]
            item = prm[2]
            if name == '群友':
                return '唔得，一个一个查'
            steamdata = loadjson(STEAM)
            memberdata = loadjson(MEMBER)
            wi = whois.Whois()
            obj = wi.object_explainer(group, user, name)
            name = obj['name'] or name
            id3 = steamdata['subscribers'].get(obj['uid'])
            if not id3:
                if obj['uid'] == UNKNOWN:
                    return f'我们群里有{name}吗？'
                return f'查不了，{name}可能还没有绑定SteamID'
            j = requests.get(OPENDOTA_PLAYERS.format(id3) + '/heroes').json()
            if item == '常用英雄':
                hero_stat = []
                if j[0]['games'] == 0:
                    return f'这个{name}是不是什么都没玩过啊'
                for i in range(5):
                    if j[i]['games'] > 0:
                        hero = HEROES_CHINESE[int(j[i]["hero_id"])][0]
                        games = j[i]["games"]
                        win = j[i]["win"]
                        win_rate = 100 * win / games
                        hero_stat.append(f'{games}局{hero}，赢了{win}局，胜率{win_rate:.2f}%')
                    else:
                        break
                return f'{name}玩得最多的{len(hero_stat)}个英雄：\n' + '\n'.join(hero_stat)
            if item == '英雄池':
                hero_num = 0
                hero_ge20 = 0
                if j[0]['games'] == 0:
                    return f'这个{name}什么都没玩过啊哪来的英雄池'
                for i in range(len(j)):
                    if j[i]['games'] > 0:
                        hero_num += 1
                        if j[i]['games'] >= 20:
                            hero_ge20 += 1
                    else:
                        break
                return f'{name}玩过{hero_num}个英雄，其中大于等于20局的有{hero_ge20}个'


    def jobs(self):
        trigger = CronTrigger(minute='*', second='30')
        job = (trigger, self.send_news_async)
        return (job,)

    async def send_news_async(self):
        steamdata = loadjson(STEAM)
        groups = steamdata.get('subscribe_groups')
        if not groups:
            return None
        news = await self.get_news_async()
        sends = []
        for msg in news:
            for g in groups:
                if str(g) in msg['target_groups']:
                    sends.append({
                        'message_type': 'group',
                        'group_id': g,
                        'message': msg['message']
                    })
        return sends

    async def get_news_async(self):
        '''
        返回最新消息
        '''
        news = []
        memberdata = loadjson(MEMBER)
        steamdata = loadjson(STEAM)
        players = self.get_players()
        sids = ','.join(str(p) for p in players.keys())
        now = int(datetime.now().timestamp())
        # print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), 'Steam雷达开始扫描')
        j = requests.get(PLAYER_SUMMARY.format(APIKEY, sids)).json()
        for p in j['response']['players']:
            id64 = int(p['steamid'])
            id3 = str(id64 - 76561197960265728)
            cur_game = p.get('gameextrainfo', '')
            pre_game = steamdata['players'][id3]['gameextrainfo']
            pname    = p['personaname']

            # 游戏状态更新
            if cur_game == 'Dota 2':
                steamdata['players'][id3]['last_DOTA2_action'] = max(now, steamdata['players'][id3]['last_DOTA2_action'])
            if cur_game != pre_game:
                minutes = (now - steamdata['players'][id3]['last_change']) // 60
                if cur_game:
                    if pre_game:
                        mt = f'{pname}玩了{minutes}分钟{pre_game}后，玩起了{cur_game}'
                    else:
                        mt = f'{pname}启动了{cur_game}'
                    if datetime.now().hour <= 6:
                        mt += '\n你他娘的不用睡觉吗？'
                    if datetime.now().weekday() < 5 and datetime.now().hour in range(8, 18):
                        mt += '\n见鬼，这群人都不用上班的吗'
                    news.append({
                        'message': mt,
                        'user'   : players[id64]
                    })
                else:
                    news.append({
                        'message': f'{pname}退出了{pre_game}，本次游戏时长{minutes}分钟',
                        'user'   : players[id64]
                    })
                steamdata['players'][id3]['gameextrainfo'] = cur_game
                steamdata['players'][id3]['last_change'] = now

            # DOTA2最近比赛更新
            # 每分钟请求时只请求最近3小时内有DOTA2活动的玩家的最近比赛，其余玩家的比赛仅每小时请求一次
            if steamdata['players'][id3]['last_DOTA2_action'] >= now - 10800 or datetime.now().minute == self.MINUTE:
                # print('{} 请求最近比赛更新 {}'.format(datetime.now(), id64))
                match_id, start_time = self.dota2.get_last_match(id64)
            else:
                match_id, start_time = (0, 0) # 将跳过之后的步骤
            new_match = False
            if match_id > steamdata['players'][id3]['last_DOTA2_match_id']:
                new_match = True
                steamdata['players'][id3]['last_DOTA2_action'] = max(start_time, steamdata['players'][id3]['last_DOTA2_action'])
                steamdata['players'][id3]['last_DOTA2_match_id'] = match_id
            if new_match:
                player = {
                    'nickname': pname,
                    'steam_id3' : int(id3),
                }
                if steamdata['DOTA2_matches_pool'].get(match_id, 0) != 0:
                    steamdata['DOTA2_matches_pool'][match_id]['players'].append(player)
                else:
                    steamdata['DOTA2_matches_pool'][match_id] = {
                        'request_attempts': 0,
                        'start_time': start_time,
                        'subscribers': [],
                        'players': [player]
                    }
                for qq in players[id64]:
                    if qq not in steamdata['DOTA2_matches_pool'][match_id]['subscribers']:
                        steamdata['DOTA2_matches_pool'][match_id]['subscribers'].append(qq)

            # 每3小时请求一次天梯段位
            if datetime.now().hour % 3 == 0 and datetime.now().minute == self.MINUTE:
                pname, cur_rank = self.dota2.get_rank_tier(id3)
                pre_rank = steamdata['players'][id3]['DOTA2_rank_tier']
                if cur_rank != pre_rank:
                    if cur_rank:
                        if pre_rank:
                            word = '升' if cur_rank > pre_rank else '掉'
                            mt = '{}从{}{}{}到了{}{}'.format(
                                pname,
                                PLAYER_RANK[pre_rank // 10], pre_rank % 10 or '',
                                word,
                                PLAYER_RANK[cur_rank // 10], cur_rank % 10 or ''
                            )
                        else:
                            mt = '{}达到了{}{}'.format(pname, PLAYER_RANK[cur_rank // 10], cur_rank % 10 or '')
                        news.append({
                            'message': mt,
                            'user'   : players[id64]
                        })
                    else:
                        pass
                    steamdata['players'][id3]['DOTA2_rank_tier'] = cur_rank

        dumpjson(steamdata, STEAM)

        news += self.dota2.get_matches_report()

        if len(news) > 0:
            print(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), f'Steam雷达扫描到了{len(news)}个新事件')

        for msg in news:
            msg['target_groups'] = []
            for u in msg['user']:
                for g in memberdata:
                    if u in memberdata[g] and g not in msg['target_groups']:
                        msg['target_groups'].append(g)

        return news


    def get_players(self):
        steamdata  = loadjson(STEAM)
        players = {}
        for p in steamdata['players'].values():
            players[p['steam_id64']] = p['subscribers']
        return players


class Dota2:
    @staticmethod
    def get_last_match(id64):
        try:
            match = requests.get(LAST_MATCH.format(APIKEY, id64)).json()['result']['matches'][0]
            return match['match_id'], match['start_time']
        except Exception as e:
            return 0, 0

    @staticmethod
    def get_rank_tier(id3):
        try:
            j = requests.get(OPENDOTA_PLAYERS.format(id3)).json()
            name = j['profile']['personaname']
            rank = j.get('rank_tier') if j.get('rank_tier') else 0
            return name, rank
        except Exception as e:
            return '', 0

    # 根据slot判断队伍, 返回0为天辉, 1为夜魇
    @staticmethod
    def get_team_by_slot(slot):
        return slot // 100

    def get_match(self, match_id):
        MATCH = os.path.join(DOTA2_MATCHES, f'{match_id}.json')
        if os.path.exists(MATCH):
            print('{} 比赛编号 {} 读取本地保存的分析结果'.format(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), match_id))
            return loadjson(MATCH)
        steamdata = loadjson(STEAM)
        try:
            match = requests.get(OPENDOTA_MATCHES.format(match_id)).json()
            if match_id in steamdata['DOTA2_matches_pool']:
                if steamdata['DOTA2_matches_pool'][match_id]['request_attempts'] >= MAX_ATTEMPTS:
                    print('{} 比赛编号 {} 重试次数过多，跳过分析'.format(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), match_id))
                    if not match.get('players'):
                        print('{} 比赛编号 {} 从OPENDOTA获取不到分析结果，使用Value的API'.format(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), match_id))
                        match = requests.get(MATCH_DETAILS.format(APIKEY, match_id)).json()['result']
                    match['incomplete'] = True
                    dumpjson(match, MATCH)
                    return match
            if match['game_mode'] in (15, 19):
                # 活动模式
                print('{} 比赛编号 {} 活动模式，跳过分析'.format(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), match_id))
                match['incomplete'] = True
                dumpjson(match, MATCH)
                return match
            received = match['players'][0]['damage_inflictor_received']
        except Exception as e:
            attempts = ''
            if match_id in steamdata['DOTA2_matches_pool']:
                steamdata['DOTA2_matches_pool'][match_id]['request_attempts'] += 1
                attempts = '（第{}次）'.format(steamdata['DOTA2_matches_pool'][match_id]['request_attempts'])
            print('{} {}{} {}'.format(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), match_id, attempts, e))
            dumpjson(steamdata, STEAM)
            return {}
        if received is None:
            # 比赛分析结果不完整
            job_id = steamdata['DOTA2_matches_pool'][match_id].get('job_id')
            if job_id:
                # 存在之前请求分析的job_id，则查询这个job是否已完成
                j = requests.get(OPENDOTA_REQUEST.format(job_id)).json()
                if j:
                    # 查询返回了数据，说明job仍未完成
                    print('{} job_id {} 仍在处理中'.format(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), job_id))
                    return {}
                else:
                    # job完成了，可以删掉
                    del steamdata['DOTA2_matches_pool'][match_id]['job_id']
                    dumpjson(steamdata, STEAM)
                    return {}
            else:
                # 不存在之前请求分析的job_id，重新请求一次，保存，下次再确认这个job是否已完成
                attempts = ''
                if match_id in steamdata['DOTA2_matches_pool']:
                    steamdata['DOTA2_matches_pool'][match_id]['request_attempts'] += 1
                    attempts = '（第{}次）'.format(steamdata['DOTA2_matches_pool'][match_id]['request_attempts'])
                j = requests.post(OPENDOTA_REQUEST.format(match_id)).json()
                job_id = j['job']['jobId']
                print('{} 比赛编号 {} 请求OPENDOTA分析{}，job_id: {}'.format(
                    datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'),
                    match_id, attempts, job_id
                ))
                if match_id in steamdata['DOTA2_matches_pool']:
                    steamdata['DOTA2_matches_pool'][match_id]['job_id'] = job_id
                    dumpjson(steamdata, STEAM)
                return {}
        else:
            # 比赛分析结果完整了
            print('{} 比赛编号 {} 从OPENDOTA获取到分析结果'.format(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), match_id))
            dumpjson(match, MATCH)
            return match

    def get_image(self, img_path):
        try:
            return Image.open(os.path.join(IMAGES, img_path))
        except Exception as e:
            print(e)
            return Image.new('RGBA', (30, 30), (255, 160, 160))

    def init_player(self, player):
        if not player.get('net_worth'):
            player['net_worth'] = 0
        if not player.get('total_xp'):
            player['total_xp'] = 0
        if not player.get('damage_inflictor_received'):
            player['damage_inflictor_received'] = {}
        if not player.get('hero_healing'):
            player['hero_healing'] = 0
        if not player.get('stuns'):
            player['stuns'] = 0
        if not player.get('purchase_log'):
            player['purchase_log'] = []
        if not player.get('item_usage'):
            player['item_usage'] = {}

    def draw_title(self, match, draw, font, item, title, color):
        idx = item[0]
        draw.text(
            (match['players'][idx]['title_position'][0], match['players'][idx]['title_position'][1]),
            title, font=font, fill=color
        )
        title_size = font.getsize(title)
        match['players'][idx]['title_position'][0] += title_size[0] + 1
        if match['players'][idx]['title_position'][0] > 195:
            match['players'][idx]['title_position'][0] = 115
            match['players'][idx]['title_position'][1] += 14


    def generate_match_message(self, match_id):
        match = self.get_match(match_id)
        if not match:
            return None
        for p in match['players']:
            self.init_player(p)
        steamdata = loadjson(STEAM)
        players = steamdata['DOTA2_matches_pool'][match_id]['players']
        start_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(match['start_time']))
        duration = match['duration']

        # 比赛模式
        mode_id = match['game_mode']
        mode = GAME_MODE[mode_id] if mode_id in GAME_MODE else '未知'

        lobby_id = match['lobby_type']
        lobby = LOBBY[lobby_id] if lobby_id in LOBBY else '未知'
        # 更新玩家对象的比赛信息
        for i in players:
            for j in match['players']:
                if i['steam_id3'] == j['account_id']:
                    i['dota2_kill'] = j['kills']
                    i['dota2_death'] = j['deaths']
                    i['dota2_assist'] = j['assists']
                    i['kda'] = ((1. * i['dota2_kill'] + i['dota2_assist']) / i['dota2_death']) \
                        if i['dota2_death'] != 0 else (1. * i['dota2_kill'] + i['dota2_assist'])
                    i['dota2_team'] = self.get_team_by_slot(j['player_slot'])
                    i['hero'] = j['hero_id']
                    i['last_hit'] = j['last_hits']
                    i['damage'] = j['hero_damage']
                    i['gpm'] = j['gold_per_min']
                    i['xpm'] = j['xp_per_min']
                    break
        nicknames = '，'.join([players[i]['nickname'] for i in range(-len(players),-1)])
        if nicknames:
            nicknames += '和'
        nicknames += players[-1]['nickname']

        # 队伍信息
        team = players[0]['dota2_team']
        win = match['radiant_win'] == (team == 0)

        team_damage = 0
        team_score = [match['radiant_score'], match['dire_score']][team]
        team_deaths = 0
        for i in match['players']:
            if self.get_team_by_slot(i['player_slot']) == team:
                team_damage += i['hero_damage']
                team_deaths += i['deaths']

        top_kda = 0
        for i in players:
            if i['kda'] > top_kda:
                top_kda = i['kda']

        if (win and top_kda > 5) or (not win and top_kda > 3):
            postive = True
        elif (win and top_kda < 2) or (not win and top_kda < 1):
            postive = False
        else:
            if random.randint(0, 1) == 0:
                postive = True
            else:
                postive = False

        tosend = []
        if win and postive:
            tosend.append(random.choice(WIN_POSTIVE).format(nicknames))
        elif win and not postive:
            tosend.append(random.choice(WIN_NEGATIVE).format(nicknames))
        elif not win and postive:
            tosend.append(random.choice(LOSE_POSTIVE).format(nicknames))
        else:
            tosend.append(random.choice(LOSE_NEGATIVE).format(nicknames))

        tosend.append('开始时间: {}'.format(start_time))
        tosend.append('持续时间: {:.0f}分{:.0f}秒'.format(duration / 60, duration % 60))
        tosend.append('游戏模式: [{}/{}]'.format(mode, lobby))

        for i in players:
            nickname = i['nickname']
            hero = random.choice(HEROES_CHINESE[i['hero']]) if i['hero'] in HEROES_CHINESE else '不知道什么鬼'
            kda = i['kda']
            last_hits = i['last_hit']
            damage = i['damage']
            kills, deaths, assists = i['dota2_kill'], i['dota2_death'], i['dota2_assist']
            gpm, xpm = i['gpm'], i['xpm']

            damage_rate = 0 if team_damage == 0 else (100 * damage / team_damage)
            participation = 0 if team_score == 0 else (100 * (kills + assists) / team_score)
            deaths_rate = 0 if team_deaths == 0 else (100 * deaths / team_deaths)

            tosend.append(
                '{}使用{}, KDA: {:.2f}[{}/{}/{}], GPM/XPM: {}/{}, ' \
                '补刀数: {}, 总伤害: {}({:.2f}%), ' \
                '参战率: {:.2f}%, 参葬率: {:.2f}%' \
                .format(nickname, hero, kda, kills, deaths, assists, gpm, xpm, last_hits,
                        damage, damage_rate,
                        participation, deaths_rate)
            )

        return '\n'.join(tosend)

    def generate_match_image(self, match_id):
        match = self.get_match(match_id)
        if not match:
            return None
        image = Image.new('RGB', (800, 900), (255, 255, 255))
        font = ImageFont.truetype(os.path.expanduser('~/.kusa/fonts/MSYH.TTC'), 12)
        font2 = ImageFont.truetype(os.path.expanduser('~/.kusa/fonts/MSYH.TTC'), 18)
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 800, 70), 'black')
        title = '比赛 ' + str(match['match_id'])
        # 手动加粗
        draw.text((30, 15), title, font=font2, fill=(255, 255, 255))
        draw.text((31, 15), title, font=font2, fill=(255, 255, 255))
        draw.text((250, 20), '开始时间', font=font, fill=(255, 255, 255))
        draw.text((251, 20), '开始时间', font=font, fill=(255, 255, 255))
        draw.text((400, 20), '持续时间', font=font, fill=(255, 255, 255))
        draw.text((401, 20), '持续时间', font=font, fill=(255, 255, 255))
        draw.text((480, 20), 'Level', font=font, fill=(255, 255, 255))
        draw.text((481, 20), 'Level', font=font, fill=(255, 255, 255))
        draw.text((560, 20), '地区', font=font, fill=(255, 255, 255))
        draw.text((561, 20), '地区', font=font, fill=(255, 255, 255))
        draw.text((650, 20), '比赛模式', font=font, fill=(255, 255, 255))
        draw.text((651, 20), '比赛模式', font=font, fill=(255, 255, 255))
        start_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(match['start_time']))
        duration = '{}分{}秒'.format(match['duration'] // 60, match['duration'] % 60)
        skill = SKILL_LEVEL[match['skill']] if match.get('skill') else 'Unknown'
        region_id = 'region_{}'.format(match.get('region'))
        region = REGION[region_id] if region_id in REGION else '未知'
        mode_id = match['game_mode']
        mode = GAME_MODE[mode_id] if mode_id in GAME_MODE else '未知'
        lobby_id = match['lobby_type']
        lobby = LOBBY[lobby_id] if lobby_id in LOBBY else '未知'
        draw.text((250, 40), start_time, font=font, fill=(255, 255, 255))
        draw.text((400, 40), duration, font=font, fill=(255, 255, 255))
        draw.text((480, 40), skill, font=font, fill=(255, 255, 255))
        draw.text((560, 40), region, font=font, fill=(255, 255, 255))
        draw.text((650, 40), f'{mode}/{lobby}', font=font, fill=(255, 255, 255))
        if match.get('incomplete'):
            draw.text((30, 40), '※分析结果不完整', font=font, fill=(255, 180, 0))
        else:
            draw.text((30, 40), '※录像分析成功', font=font, fill=(123, 163, 52))
        RADIANT_GREEN = (60, 144, 40)
        DIRE_RED = (156, 54, 40)
        winner = 1 - int(match['radiant_win'])
        draw.text((364, 81), SLOT_CHINESE[winner] + '胜利', font=font2, fill=[RADIANT_GREEN, DIRE_RED][winner])
        draw.text((365, 81), SLOT_CHINESE[winner] + '胜利', font=font2, fill=[RADIANT_GREEN, DIRE_RED][winner])
        radiant_score = str(match['radiant_score'])
        radiant_score_size = font2.getsize(radiant_score)
        draw.text((338 - radiant_score_size[0], 81), radiant_score, font=font2, fill=RADIANT_GREEN)
        draw.text((339 - radiant_score_size[0], 81), radiant_score, font=font2, fill=RADIANT_GREEN)
        draw.text((460, 81), str(match['dire_score']), font=font2, fill=DIRE_RED)
        draw.text((461, 81), str(match['dire_score']), font=font2, fill=DIRE_RED)
        draw.rectangle((0, 120, 800, 122), RADIANT_GREEN)
        draw.rectangle((0, 122, 120, 162), RADIANT_GREEN)
        draw.polygon([(120, 122), (160, 122), (120, 162)], RADIANT_GREEN)
        draw.rectangle((0, 505, 800, 507), DIRE_RED)
        draw.rectangle((0, 507, 120, 547), DIRE_RED)
        draw.polygon([(120, 507), (160, 507), (120, 547)], DIRE_RED)
        draw.text((80, 513 - 385 * int(match['radiant_win'])), '胜利', font=font2, fill=(255, 255, 255))
        draw.text((80, 128 + 385 * int(match['radiant_win'])), '失败', font=font2, fill=(255, 255, 255))
        max_net = [0, 0]
        max_xpm = [0, 0]
        max_kills = [0, 0, 0]
        max_deaths = [0, 0, 99999]
        max_assists = [0, 0, 0]
        max_hero_damage = [0, 0]
        max_tower_damage = [0, 0]
        max_stuns = [0, 0]
        max_healing = [0, 0]
        max_hurt = [0, 0]
        min_participation = [0, 999, 999999]
        for slot in range(0, 2):
            team_damage = 0
            team_damage_received = 0
            team_score = [match['radiant_score'], match['dire_score']][slot]
            team_kills = 0
            team_deaths = 0
            team_gold = 0
            team_exp = 0
            max_mvp_point = [0, 0]
            draw.text((20, 126 + slot * 385), SLOT[slot],         font=font, fill=(255, 255, 255))
            draw.text((20, 140 + slot * 385), SLOT_CHINESE[slot], font=font, fill=(255, 255, 255))
            for i in range(5):
                idx = slot * 5 + i
                p = match['players'][idx]
                self.init_player(p)
                p['hurt'] = sum(p['damage_inflictor_received'].values())
                p['participation'] = 0 if team_score == 0 else 100 * (p['kills'] + p['assists']) / team_score
                team_damage += p['hero_damage']
                team_damage_received += p['hurt']
                team_kills += p['kills']
                team_deaths += p['deaths']
                team_gold += p['net_worth']
                team_exp += p['total_xp']
                hero_img = self.get_image('{}_full.png'.format(HEROES[p['hero_id']]))
                hero_img = hero_img.resize((60, 33), Image.ANTIALIAS)
                image.paste(hero_img, (10, 170 + slot * 70 + idx * 65))
                draw.rectangle((50, 188 + slot * 70 + idx * 65, 69, 202 + slot * 70 + idx * 65), fill=(50, 50, 50))
                level = str(p['level'])
                level_size = font.getsize(level)
                draw.text((67 - level_size[0], 187 + slot * 70 + idx * 65), level, font=font, fill=(255, 255, 255))
                rank = p.get('rank_tier') if p.get('rank_tier') else 0
                rank, star = rank // 10, rank % 10
                rank_img = self.get_image(f'rank_icon_{rank}.png')
                if star:
                    rank_star = self.get_image(f'rank_star_{star}.png')
                    rank_img = Image.alpha_composite(rank_img, rank_star)
                rank_img = Image.alpha_composite(Image.new('RGBA', rank_img.size, (255, 255, 255)), rank_img)
                rank_img = rank_img.convert('RGB')
                rank_img = rank_img.resize((45, 45), Image.ANTIALIAS)
                image.paste(rank_img, (70, 164 + slot * 70 + idx * 65))
                rank = '[{}{}] '.format(PLAYER_RANK[rank], star if star else '')
                rank_size = font.getsize(rank)
                draw.text((115, 167 + slot * 70 + idx * 65), rank, font=font, fill=(128, 128, 128))
                pname = p.get('personaname') if p.get('personaname') else '匿名玩家'
                pname_size = font.getsize(pname)
                while rank_size[0] + pname_size[0] > 240:
                    pname = pname[:-2] + '…'
                    pname_size = font.getsize(pname)
                draw.text((115 + rank_size[0], 167 + slot * 70 + idx * 65), pname, font=font, fill=[RADIANT_GREEN, DIRE_RED][slot])
                net = '{:,}'.format(p['net_worth'])
                net_size = font.getsize(net)
                damage_to_net = '({:.2f})'.format(p['hero_damage'] / p['net_worth'] if p['net_worth'] else 0)
                draw.text((116, 182 + slot * 70 + idx * 65), net, font=font, fill=(0, 0, 0))
                draw.text((115, 181 + slot * 70 + idx * 65), net, font=font, fill=(255, 255, 0))
                draw.text((119 + net_size[0], 181 + slot * 70 + idx * 65), damage_to_net, font=font, fill=(0, 0, 0))

                draw.text((215, 209 + slot * 70 + idx * 65), '建筑伤害: {:,}'.format(p['tower_damage']), font=font, fill=(0, 0, 0))
                kda = '{}/{}/{} ({:.2f})'.format(
                    p['kills'], p['deaths'], p['assists'],
                    (p['kills'] + p['assists']) if p['deaths'] == 0 else (p['kills'] + p['assists']) / p['deaths']
                )
                draw.text((375, 167 + slot * 70 + idx * 65), kda, font=font, fill=(0, 0, 0))
                draw.text((375, 195 + slot * 70 + idx * 65), '控制时间: {:.2f}s'.format(p['stuns']), font=font, fill=(0, 0, 0))
                draw.text((375, 209 + slot * 70 + idx * 65), '治疗量: {:,}'.format(p['hero_healing']), font=font, fill=(0, 0, 0))

                p['title_position'] = [115, 195 + slot * 70 + idx * 65]
                mvp_point = p['kills'] * 5 + p['assists'] * 3 + p['stuns'] * 0.5 + p['hero_damage'] * 0.001 + p['tower_damage'] * 0.002 + p['hero_healing'] * 0.002
                if mvp_point > max_mvp_point[1]:
                    max_mvp_point = [idx, mvp_point]
                if p['net_worth'] > max_net[1]:
                    max_net = [idx, p['net_worth']]
                if p['xp_per_min'] > max_xpm[1]:
                    max_xpm = [idx, p['xp_per_min']]
                if p['kills'] > max_kills[1] or (p['kills'] == max_kills[1] and p['hero_damage'] > max_kills[2]):
                    max_kills = [idx, p['kills'], p['hero_damage']]
                if p['deaths'] > max_deaths[1] or (p['deaths'] == max_deaths[1] and p['net_worth'] < max_deaths[2]):
                    max_deaths = [idx, p['deaths'], p['net_worth']]
                if p['assists'] > max_assists[1] or (p['assists'] == max_assists[1] and p['hero_damage'] > max_assists[2]):
                    max_assists = [idx, p['assists'], p['hero_damage']]
                if p['hero_damage'] > max_hero_damage[1]:
                    max_hero_damage = [idx, p['hero_damage']]
                if p['tower_damage'] > max_tower_damage[1]:
                    max_tower_damage = [idx, p['tower_damage']]
                if p['stuns'] > max_stuns[1]:
                    max_stuns = [idx, p['stuns']]
                if p['hero_healing'] > max_healing[1]:
                    max_healing = [idx, p['hero_healing']]
                if p['hurt'] > max_hurt[1]:
                    max_hurt = [idx, p['hurt']]
                if p['participation'] < min_participation[1] or (p['participation'] == min_participation[1] and p['hero_damage'] < min_participation[2]):
                    min_participation = [idx, p['participation'], p['hero_damage']]

                image.paste(Image.new('RGB', (252, 32), (192, 192, 192)), (474, 171 + slot * 70 + idx * 65))
                p['purchase_log'].reverse()
                for item in ITEM_SLOTS:
                    if p[item] == 0:
                        item_img = Image.new('RGB', (40, 30), (128, 128, 128))
                    else:
                        item_img = self.get_image('{}_lg.png'.format(ITEMS[p[item]]))
                    if item == 'item_neutral':
                        ima = item_img.convert('RGBA')
                        size = ima.size
                        r1 = min(size[0], size[1])
                        if size[0] != size[1]:
                            ima = ima.crop((
                                (size[0] - r1) // 2,
                                (size[1] - r1) // 2,
                                (size[0] + r1) // 2,
                                (size[1] + r1) // 2
                            ))
                        r2 = r1 // 2
                        imb = Image.new('RGBA', (r2 * 2, r2 * 2), (255, 255, 255, 0))
                        pima = ima.load()
                        pimb = imb.load()
                        r = r1 / 2
                        for i in range(r1):
                            for j in range(r1):
                                l = ((i - r) ** 2 + (j - r) ** 2) ** 0.5
                                if l < r2:
                                    pimb[i - (r - r2), j - (r - r2)] = pima[i, j]
                        imb = imb.resize((30, 30), Image.ANTIALIAS)
                        imb = Image.alpha_composite(Image.new('RGBA', imb.size, (255, 255, 255)), imb)
                        item_img = imb.convert('RGB')
                        image.paste(item_img, (729, 170 + slot * 70 + idx * 65))
                    else:
                        item_img = item_img.resize((40, 30), Image.ANTIALIAS)
                        image.paste(item_img, (475 + 42 * ITEM_SLOTS.index(item), 172 + slot * 70 + idx * 65))
                        purchase_time = None
                        for pl in p['purchase_log']:
                            if p[item] == 0:
                                continue
                            if pl['key'] == ITEMS[p[item]]:
                                purchase_time = pl['time']
                                pl['key'] += '_'
                                break
                        if purchase_time:
                            draw.rectangle((475 + 42 * ITEM_SLOTS.index(item), 191 + slot * 70 + idx * 65, 514 + 42 * ITEM_SLOTS.index(item), 201 + slot * 70 + idx * 65), fill=(50, 50, 50))
                            draw.text(
                                (479 + 42 * ITEM_SLOTS.index(item), 188 + slot * 70 + idx * 65),
                                '{:0>2}:{:0>2}'.format(purchase_time // 60, purchase_time % 60) if purchase_time > 0 else '-{}:{:0>2}'.format(-purchase_time // 60, -purchase_time % 60),
                                font=font, fill=(192, 192, 192)
                            )

                s = 1 if 'ultimate_scepter' in p['item_usage'] else 0
                scepter_img = self.get_image(f'scepter_{s}.png')
                scepter_img = scepter_img.resize((20, 20), Image.ANTIALIAS)
                image.paste(scepter_img, (765 , 170 + slot * 70 + idx * 65))
                s = 1 if 'aghanims_shard' in p['item_usage'] else 0
                shard_img = self.get_image(f'shard_{s}.png')
                shard_img = shard_img.resize((20, 11), Image.ANTIALIAS)
                image.paste(shard_img, (765 , 190 + slot * 70 + idx * 65))

            for i in range(4):
                draw.rectangle((0, 228 + slot * 395 + i * 65, 800,  228 + slot * 395 + i * 65), (225, 225, 225))

            for i in range(5):
                idx = slot * 5 + i
                p = match['players'][idx]
                damage_rate = 0 if team_damage == 0 else 100 * (p['hero_damage'] / team_damage)
                damage_received_rate = 0 if team_damage_received == 0 else 100 * (p['hurt'] / team_damage_received)
                draw.text((215, 181 + slot * 70 + idx * 65), '造成伤害: {:,} ({:.2f}%)'.format(p['hero_damage'], damage_rate), font=font, fill=(0, 0, 0))
                draw.text((215, 195 + slot * 70 + idx * 65), '承受伤害: {:,} ({:.2f}%)'.format(p['hurt'], damage_received_rate), font=font, fill=(0, 0, 0))
                draw.text((375, 181 + slot * 70 + idx * 65), '参战率: {:.2f}%'.format(p['participation']), font=font, fill=(0, 0, 0))

            if slot == winner:
                self.draw_title(match, draw, font, max_mvp_point, 'MVP', (255, 127, 39))
            else:
                self.draw_title(match, draw, font, max_mvp_point, '魂', (0, 162, 232))

            draw.text((475, 128 + slot * 385), '杀敌', font=font, fill=(64, 64, 64))
            draw.text((552, 128 + slot * 385), '总伤害', font=font, fill=(64, 64, 64))
            draw.text((636, 128 + slot * 385), '总经济', font=font, fill=(64, 64, 64))
            draw.text((726, 128 + slot * 385), '总经验', font=font, fill=(64, 64, 64))
            draw.text((475, 142 + slot * 385), f'{team_kills}', font=font, fill=(128, 128, 128))
            draw.text((552, 142 + slot * 385), f'{team_damage}', font=font, fill=(128, 128, 128))
            draw.text((636, 142 + slot * 385), f'{team_gold}', font=font, fill=(128, 128, 128))
            draw.text((726, 142 + slot * 385), f'{team_exp}', font=font, fill=(128, 128, 128))

        if max_net[1] > 0:
            self.draw_title(match, draw, font, max_net, '富', (255, 192, 30))
        if max_xpm[1] > 0:
            self.draw_title(match, draw, font, max_xpm, '睿', (30, 30, 255))
        if max_stuns[1] > 0:
            self.draw_title(match, draw, font, max_stuns, '控', (255, 0, 128))
        if max_hero_damage[1] > 0:
            self.draw_title(match, draw, font, max_hero_damage, '爆', (192, 0, 255))
        if max_kills[1] > 0:
            self.draw_title(match, draw, font, max_kills, '破', (224, 36, 36))
        if max_deaths[1] > 0:
            self.draw_title(match, draw, font, max_deaths, '鬼', (192, 192, 192))
        if max_assists[1] > 0:
            self.draw_title(match, draw, font, max_assists, '助', (0, 132, 66))
        if max_tower_damage[1] > 0:
            self.draw_title(match, draw, font, max_tower_damage, '拆', (128, 0, 255))
        if max_healing[1] > 0:
            self.draw_title(match, draw, font, max_healing, '奶', (0, 228, 120))
        if max_hurt[1] > 0:
            self.draw_title(match, draw, font, max_hurt, '耐', (112, 146, 190))
        if min_participation[1] < 999:
            self.draw_title(match, draw, font, min_participation, '摸', (200, 190, 230))

        draw.text(
            (10, 882),
            '※录像分析数据来自opendota.com，DOTA2游戏图片素材版权归Value所有',
            font=font,
            fill=(128, 128, 128)
        )
        image.save(os.path.join(DOTA2_MATCHES, f'{match_id}.png'), 'png')
        print('{} 比赛编号 {} 生成战报图片'.format(datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), match_id))

    def get_matches_report(self):
        steamdata = loadjson(STEAM)
        reports = []
        todelete = []
        for match_id, match_info in steamdata['DOTA2_matches_pool'].items():
            now = int(datetime.now().timestamp())
            if match_info['start_time'] <= now - 86400 * 7:
                todelete.append(match_id)
                continue
            m = self.generate_match_message(match_id)
            if isinstance(m, str):
                self.generate_match_image(match_id)
                m += '\n[CQ:image,file=file:///{}]'.format(os.path.join(DOTA2_MATCHES, f'{match_id}.png'))
                reports.append(
                    {
                        'message': m,
                        'user'   : match_info['subscribers']
                    }
                )
                todelete.append(match_id)
        # 数据在生成比赛报告的过程中会被修改，需要重新读取
        steamdata = loadjson(STEAM)
        for match_id in todelete:
            del steamdata['DOTA2_matches_pool'][match_id]
        dumpjson(steamdata, STEAM)
        return reports