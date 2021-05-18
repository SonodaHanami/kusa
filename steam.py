import json
import os
import random
import pygtrie
import re
import requests
import sys
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
MAX_ATTEMPTS = 10
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
            try:
                if prm[1]:
                    return usage
                id3 = int(prm[2])
                if id3 > 76561197960265728:
                    id3 -= 76561197960265728
                id64 = id3 + 76561197960265728
                steamdata = loadjson(STEAM)
                steamdata[user] = {
                    "steam_id_short": id3,
                    "steam_id_long": id64,
                    "last_DOTA2_match_ID": 0,
                    "last_change": 0,
                    "gameextrainfo": "",
                }
                dumpjson(steamdata, STEAM)
                return '绑定成功'
            except:
                return usage

        if msg.lower() == '解除绑定steam':
            steamdata = loadjson(STEAM)
            if steamdata.get(user):
                del steamdata[user]
                dumpjson(steamdata, STEAM)
                return '解除绑定成功'
            else:
                return '没有找到你的绑定记录'

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
                players = self.get_players()
                players2 = []
                for p in players.keys():
                    for q in players[p]:
                        if q in memberdata[group]:
                            players2.append(p - 76561197960265728)
                players2 = list(set(players2))
            else:
                is_solo = True
                wi = whois.Whois()
                obj = wi.object_explainer(group, user, name)
                steam_info = steamdata.get(obj['uid'])
                if steam_info:
                    sid = steam_info.get('steam_id_short')
                    if not sid:
                        return IDK
                else: # steam_info is None
                    if obj['uid'] == UNKNOWN:
                        return f'我们群里有{name}吗？'
                    return f'{IDK}，因为{obj["name"]}还没有绑定SteamID'
                players2 = [sid]
            ranks = []
            replys = []
            for sid in players2:
                j = requests.get(OPENDOTA_PLAYERS.format(sid)).json()
                rank = j.get('rank_tier') if j.get('rank_tier') else 0
                if rank:
                    ranks.append((j['profile']['personaname'], rank))
            if ranks:
                ranks = sorted(ranks, key=lambda i: i[1], reverse=True)
                for name, rank in ranks:
                    replys.append('{}现在是{}{}'.format(name, PLAYER_RANK[rank // 10], rank % 10 or ''))
                if len(replys) > 2:
                    replys.append('大家都有光明的未来！')
                return '\n'.join(replys)
            else:
                return '查不到哟'

        prm = re.match('(.+)在(干|做|搞|整)(嘛|啥|哈|什么)', msg)
        if prm:
            name = prm[1].strip()
            steamdata = loadjson(STEAM)
            memberdata = loadjson(MEMBER)
            if re.search('群友', name):
                is_solo = False
                players = self.get_players()
                players2 = []
                for p in players.keys():
                    for q in players[p]:
                        if q in memberdata[group]:
                            players2.append(p)
                players2 = list(set(players2))
                sids = ','.join(str(p) for p in players2)
            else:
                is_solo = True
                wi = whois.Whois()
                obj = wi.object_explainer(group, user, name)
                steam_info = steamdata.get(obj['uid'])
                if steam_info:
                    sids = steam_info.get('steam_id_long')
                    if not sids:
                        return IDK
                else: # steam_info is None
                    # if obj['uid'] not in data[group]:
                    if obj['uid'] == UNKNOWN:
                        return f'我们群里有{name}吗？'
                    return f'{IDK}，因为{obj["name"]}还没有绑定SteamID'
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
                        "message_type": "group",
                        "group_id": g,
                        "message": msg['message']
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
        status_changed = False
        sids = ','.join(str(p) for p in players.keys())
        # print('{} 请求玩家状态更新 {}'.format(datetime.now(), sids))
        j = requests.get(PLAYER_SUMMARY.format(APIKEY, sids)).json()
        for p in j['response']['players']:
            sid = int(p['steamid'])
            for qq in players[sid]:
                cur_game = p.get('gameextrainfo', '')
                pre_game = steamdata[qq]['gameextrainfo']
                pname    = p['personaname']

                # 游戏状态更新
                if cur_game != pre_game:
                    status_changed = True
                    now = int(datetime.now().timestamp())
                    minutes = (now - steamdata[qq]['last_change']) // 60
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
                            'user'   : [qq]
                        })
                    else:
                        news.append({
                            'message': f'{pname}退出了{pre_game}，本次游戏时长{minutes}分钟',
                            'user'   : [qq]
                        })
                    steamdata[qq]['gameextrainfo'] = cur_game
                    steamdata[qq]['last_change'] = now

            # DOTA2最近比赛更新
            # print('{} 请求最近比赛更新 {}'.format(datetime.now(), sid))
            match_id, start_time = self.dota2.get_last_match(sid)
            new_match = False
            for qq in players[sid]:
                if match_id > steamdata[qq]['last_DOTA2_match_ID']:
                    new_match = True
                    steamdata[qq]['last_DOTA2_match_ID'] = match_id
            if new_match:
                status_changed = True
                player = {
                    'nickname': pname,
                    'steam_id3' : sid - 76561197960265728,
                    'steam_id64' : sid,
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
                for qq in players[sid]:
                    if qq not in steamdata['DOTA2_matches_pool'][match_id]['subscribers']:
                        steamdata['DOTA2_matches_pool'][match_id]['subscribers'].append(qq)

        if status_changed:
            dumpjson(steamdata, STEAM)

        news += self.dota2.get_matches_report()

        for msg in news:
            msg['target_groups'] = []
            for u in msg['user']:
                for g in memberdata:
                    if u in memberdata[g] and g not in msg['target_groups']:
                        msg['target_groups'].append(g)

        return news


    def get_players(self):
        memberdata = loadjson(MEMBER)
        steamdata  = loadjson(STEAM)
        players = {}
        for g in memberdata:
            for qq in memberdata.get(g):
                steam_info = steamdata.get(qq)
                if steam_info:
                    sid = steam_info.get('steam_id_long')
                    if sid:
                        if sid not in players:
                            players[sid] = [qq]
                        else:
                            players[sid].append(qq)
        return players


class Dota2:
    @staticmethod
    def get_last_match(id64):
        try:
            match = requests.get(LAST_MATCH.format(APIKEY, id64)).json()['result']['matches'][0]
            return match['match_id'], match['start_time']
        except Exception as e:
            return 0, 0

    # 根据slot判断队伍, 返回1为天辉, 2为夜魇
    @staticmethod
    def get_team_by_slot(slot):
        if slot < 100:
            return 1
        else:
            return 2

    def request_match(self, match_id):
        j = requests.post(OPENDOTA_REQUEST.format(match_id)).json()
        job_id = j['job']['jobId']
        print('{} 比赛编号 {} 请求OPENDOTA分析，job_id: {}'.format(datetime.now(), match_id, job_id))
        return job_id

    def get_match(self, match_id):
        MATCH = os.path.join(DOTA2_MATCHES, f'{match_id}.json')
        if os.path.exists(MATCH):
            print('{} 比赛编号 {} 读取本地保存的分析结果'.format(datetime.now(), match_id))
            return loadjson(MATCH)
        steamdata = loadjson(STEAM)
        try:
            if steamdata['DOTA2_matches_pool'][match_id]['request_attempts'] > MAX_ATTEMPTS:
                return requests.get(MATCH_DETAILS.format(APIKEY, match_id)).json()['result']
            match = requests.get(OPENDOTA_MATCHES.format(match_id)).json()
            received = match['players'][0]['damage_inflictor_received']
        except Exception as e:
            print('{} {} {}'.format(datetime.now(), match_id, e))
            steamdata['DOTA2_matches_pool'][match_id]['request_attempts'] += 1
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
                    print('{} job_id {} 仍在处理中'.format(datetime.now(), job_id))
                    return {}
                else:
                    # job完成了，可以删掉
                    del steamdata['DOTA2_matches_pool'][match_id]['job_id']
                    dumpjson(steamdata, STEAM)
                    return {}
            else:
                # 不存在之前请求分析的job_id，重新请求一次，保存，下次再确认这个job是否已完成
                job_id = self.request_match(match_id)
                steamdata['DOTA2_matches_pool'][match_id]['job_id'] = job_id
                steamdata['DOTA2_matches_pool'][match_id]['request_attempts'] += 1
                dumpjson(steamdata, STEAM)
                return {}
        else:
            # 比赛分析结果完整了
            print('{} 比赛编号 {} 从OPENDOTA获取到分析结果'.format(datetime.now(), match_id))
            dumpjson(match, MATCH)
            return match

    def get_image(self, img_path):
        try:
            return Image.open(os.path.join(IMAGES, img_path))
        except Exception as e:
            print(e)
            return Image.new('RGBA', (30, 30), (255, 160, 160))


    def generate_match_message(self, match_id):
        match = self.get_match(match_id)
        if not match:
            return None
        steamdata = loadjson(STEAM)
        players = steamdata['DOTA2_matches_pool'][match_id]['players']
        start_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(match['start_time']))
        duration = match['duration']

        # 比赛模式
        mode_id = match["game_mode"]
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
        win = match['radiant_win'] == (team == 1)

        if mode_id in (15, 19):  # 各种活动模式仅简略通报
            return f'{nicknames}玩了一把[{mode}/{lobby}]，开始于{start_time}，' \
                f'持续{duration/60:.0f}分{duration%60:.0f}秒，' \
                f'看起来好像是{"赢" if win else "输"}了。'

        team_damage = 0
        team_kills = 0
        team_deaths = 0
        for i in match['players']:
            if self.get_team_by_slot(i['player_slot']) == team:
                team_damage += i['hero_damage']
                team_kills += i['kills']
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

            damage_rate = 0 if team_damage == 0 else (100 * (float(damage) / team_damage))
            participation = 0 if team_kills == 0 else (100 * float(kills + assists) / team_kills)
            deaths_rate = 0 if team_deaths == 0 else (100 * float(deaths) / team_deaths)

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
        image = Image.new('RGB', (800, 800), (255, 255, 255))
        font = ImageFont.truetype(os.path.expanduser('~/.kusa/MSYH.TTC'), 12)
        font2 = ImageFont.truetype(os.path.expanduser('~/.kusa/MSYH.TTC'), 18)
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 800, 100), 'black')
        title = '比赛 ' + str(match['match_id'])
        title_size = font2.getsize(title)
        # 手动加粗
        draw.text(((800 - title_size[0]) / 2    , 10), title, font=font2, fill=(255, 255, 255))
        draw.text(((800 - title_size[0]) / 2 + 1, 10), title, font=font2, fill=(255, 255, 255))
        draw.text((20, 50), '开始时间', font=font, fill=(255, 255, 255))
        draw.text((21, 50), '开始时间', font=font, fill=(255, 255, 255))
        draw.text((200, 50), '持续时间', font=font, fill=(255, 255, 255))
        draw.text((201, 50), '持续时间', font=font, fill=(255, 255, 255))
        draw.text((360, 50), 'Level', font=font, fill=(255, 255, 255))
        draw.text((361, 50), 'Level', font=font, fill=(255, 255, 255))
        draw.text((500, 50), '地区', font=font, fill=(255, 255, 255))
        draw.text((501, 50), '地区', font=font, fill=(255, 255, 255))
        draw.text((650, 50), '比赛模式', font=font, fill=(255, 255, 255))
        draw.text((651, 50), '比赛模式', font=font, fill=(255, 255, 255))
        start_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(match['start_time']))
        duration = '{}分{}秒'.format(match['duration'] // 60, match['duration'] % 60)
        skill = SKILL_LEVEL[match['skill']] if match.get('skill') else 'Unknown'
        region_id = 'region_{}'.format(match.get('region'))
        region = REGION[region_id] if region_id in REGION else '未知'
        mode_id = match["game_mode"]
        mode = GAME_MODE[mode_id] if mode_id in GAME_MODE else '未知'
        lobby_id = match['lobby_type']
        lobby = LOBBY[lobby_id] if lobby_id in LOBBY else '未知'
        draw.text((20, 70), start_time, font=font, fill=(255, 255, 255))
        draw.text((200, 70), duration, font=font, fill=(255, 255, 255))
        draw.text((360, 70), skill, font=font, fill=(255, 255, 255))
        draw.text((500, 70), region, font=font, fill=(255, 255, 255))
        draw.text((650, 70), f'{mode}/{lobby}', font=font, fill=(255, 255, 255))
        draw.rectangle((0, 120, 800, 122), (60, 144, 40))
        draw.rectangle((0, 122, 120, 162), (60, 144, 40))
        draw.polygon([(120, 122), (160, 122), (120, 162)], (60, 144, 40))
        draw.rectangle((0, 440, 800, 442), (156, 54, 40))
        draw.rectangle((0, 442, 120, 482), (156, 54, 40))
        draw.polygon([(120, 442), (160, 442), (120, 482)], (156, 54, 40))
        draw.text((80, 448 - 320 * int(match['radiant_win'])), '胜利', font=font2, fill=(255, 255, 255))
        draw.text((80, 128 + 320 * int(match['radiant_win'])), '失败', font=font2, fill=(255, 255, 255))
        for slot in range(0, 2):
            team_damage = 0
            team_damage_received = 0
            team_kills = 0
            team_deaths = 0
            team_gold = 0
            team_exp = 0
            draw.text((20, 126 + slot * 320), SLOT[slot],         font=font, fill=(255, 255, 255))
            draw.text((20, 140 + slot * 320), SLOT_CHINESE[slot], font=font, fill=(255, 255, 255))
            for i in range(0, 5):
                idx = slot * 5 + i
                p = match['players'][idx]
                team_damage += p['hero_damage']
                team_damage_received += sum(p['damage_inflictor_received'].values())
                team_kills += p['kills']
                team_deaths += p['deaths']
                team_gold += p['total_gold']
                team_exp += p['total_xp']
                hero_img = self.get_image('{}_full.png'.format(HEROES[p['hero_id']]))
                hero_img = hero_img.resize((80, 45), Image.ANTIALIAS)
                image.paste(hero_img, (20, 170 + slot * 70 + idx * 50))
                draw.rectangle((80, 200 + slot * 70 + idx * 50, 99, 214 + slot * 70 + idx * 50), fill=(50, 50, 50))
                level = str(p['level'])
                level_size = font.getsize(level)
                draw.text((97 - level_size[0], 199 + slot * 70 + idx * 50), level, font=font, fill=(255, 255, 255))
                rank = p.get('rank_tier') if p.get('rank_tier') else 0
                rank, star = rank // 10, rank % 10
                rank_img = self.get_image(f'rank_icon_{rank}.png')
                if star:
                    rank_star = self.get_image(f'rank_star_{star}.png')
                    rank_img = Image.alpha_composite(rank_img, rank_star)
                rank_img = Image.alpha_composite(Image.new('RGBA', rank_img.size, (255, 255, 255)), rank_img)
                rank_img = rank_img.convert('RGB')
                rank_img = rank_img.resize((45, 45), Image.ANTIALIAS)
                image.paste(rank_img, (100, 170 + slot * 70 + idx * 50))
                rank = '{}{}'.format(PLAYER_RANK[rank], star if star else '')
                draw.text((145, 184 + slot * 70 + idx * 50), rank, font=font, fill=(128, 128, 128))
                draw.text(
                    (145, 170 + slot * 70 + idx * 50),
                    p.get('personaname') if p.get('personaname') else '匿名',
                    font=font,
                    fill=[(60, 144, 40), (156, 54, 40)][slot]
                )

                kda = '{}/{}/{}'.format(p['kills'], p['deaths'], p['assists'])
                draw.text((370, 170 + slot * 70 + idx * 50), kda, font=font, fill=(0, 0, 0))
                kda = 'KDA:{:.2f}'.format(
                    (p['kills'] + p['assists']) if p['deaths'] == 0 else (p['kills'] + p['assists']) / p['deaths'])
                draw.text((370, 184 + slot * 70 + idx * 50), kda, font=font, fill=(0, 0, 0))

                image.paste(Image.new('RGB', (252, 32), (192, 192, 192)), (469, 169 + slot * 70 + idx * 50))
                for item in ITEM_SLOTS:
                    if p[item] == 0:
                        item_img = Image.new('RGB', (40, 30), (128, 128, 128))
                    else:
                        item_img = self.get_image('{}_lg.png'.format(ITEMS[p[item]]))
                    if item == 'item_neutral':
                        ima = item_img.convert("RGBA")
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
                        image.paste(item_img, (724, 170 + slot * 70 + idx * 50))
                    else:
                        item_img = item_img.resize((40, 30), Image.ANTIALIAS)
                        image.paste(item_img, (470 + 42 * ITEM_SLOTS.index(item), 170 + slot * 70 + idx * 50))

                s = 1 if 'ultimate_scepter' in p['item_usage'] else 0
                scepter_img = self.get_image(f'scepter_{s}.png')
                scepter_img = scepter_img.resize((20, 20), Image.ANTIALIAS)
                image.paste(scepter_img, (760 , 170 + slot * 70 + idx * 50))
                s = 1 if 'aghanims_shard' in p['item_usage'] else 0
                shard_img = self.get_image(f'shard_{s}.png')
                shard_img = shard_img.resize((20, 11), Image.ANTIALIAS)
                image.paste(shard_img, (760 , 190 + slot * 70 + idx * 50))

            for i in range(0, 5):
                idx = slot * 5 + i
                p = match['players'][idx]
                participation = 0 if team_kills == 0 else 100 * (p['kills'] + p['assists']) / team_kills
                damage_rate = 0 if team_damage == 0 else 100 * (p['hero_damage'] / team_damage)
                damage_received = sum(p['damage_inflictor_received'].values())
                damage_received_rate = 0 if team_damage_received == 0 else 100 * (damage_received / team_damage_received)
                draw.text((210, 184 + slot * 70 + idx * 50), '造成伤害: {}({:.2f}%)'.format(p['hero_damage'], damage_rate), font=font, fill=(0, 0, 0))
                draw.text((210, 198 + slot * 70 + idx * 50), '承受伤害: {}({:.2f}%)'.format(damage_received, damage_received_rate), font=font, fill=(0, 0, 0))
                draw.text((370, 198 + slot * 70 + idx * 50), '参战率: {:.2f}%'.format(participation), font=font, fill=(0, 0, 0))

            draw.text((550, 140 + slot * 320), f'杀敌 {team_kills}', font=font, fill=(128, 128, 128))
            draw.text((610, 140 + slot * 320), f'总经济 {team_gold}', font=font, fill=(128, 128, 128))
            draw.text((700, 140 + slot * 320), f'总经验 {team_exp}', font=font, fill=(128, 128, 128))

        draw.text(
            (10, 780),
            '※录像分析数据来自opendota.com，DOTA2游戏图片素材版权归Value所有',
            font=font,
            fill=(128, 128, 128)
        )
        image.save(os.path.join(DOTA2_MATCHES, f'{match_id}.png'), 'png')

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
                if match_info['request_attempts'] <= MAX_ATTEMPTS:
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