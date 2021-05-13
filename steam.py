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

        prm = re.match('(怎么)?绑定steam(.*)', msg, re.I)
        if prm:
            usage = '使用方法：\n绑定Steam Steam好友代码（9位）（也可能是8位或10位）'
            try:
                if prm[1]:
                    return usage
                id3 = int(prm[2])
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
            name = prm[1].strip()
            steamdata = loadjson(STEAM)
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
            j = requests.get(OPENDOTA_PLAYERS.format(sid)).json()
            if j.get('rank_tier'):
                return '{}现在是{}{}'.format(
                    j['profile']['personaname'],
                    PLAYER_RANK[j['rank_tier'] // 10],
                    j['rank_tier'] % 10
                )
            else:
                return '查不到哟'

        prm = re.match('(.*)在(干|做|搞|整)(嘛|啥|哈|什么)', msg)
        if prm:
            name = prm[1]
            if not name:
                return None
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
            j = requests.get(PLAYER_SUMMARY.format(APIKEY, sids)).json()
            replys = []
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
        matches = {}
        replys = []
        status_changed = False
        sids = ','.join(str(p) for p in players.keys())
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
                last_DOTA2_match_ID = self.dota2.get_last_match_id(sid)
                if last_DOTA2_match_ID > steamdata[qq]['last_DOTA2_match_ID']:
                    status_changed = True
                    steamdata[qq]['last_DOTA2_match_ID'] = last_DOTA2_match_ID
                    player = {
                        'uid': qq,
                        'nickname': pname,
                        'steam_id3' : sid - 76561197960265728,
                        'steam_id64' : sid,
                        'last_DOTA2_match_ID': last_DOTA2_match_ID
                    }
                    if matches.get(last_DOTA2_match_ID, 0) != 0:
                        matches[last_DOTA2_match_ID].append(player)
                    else:
                        matches.update({last_DOTA2_match_ID: [player]})

        for match_id in matches:
            steamdata['DOTA2_matches_pool'][match_id] = {
                'end_time': -1,
                'players': matches[match_id]
            }

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
    def get_last_match_id(id64):
        try:
            match_id = requests.get(LAST_MATCH.format(APIKEY, id64)).json()["result"]["matches"][0]["match_id"]
            return match_id
        except Exception as e:
            return 0

    # 根据slot判断队伍, 返回1为天辉, 2为夜魇
    @staticmethod
    def get_team_by_slot(slot):
        if slot < 100:
            return 1
        else:
            return 2

    def get_match_end_time(self, match_id):
        try:
            j = requests.get(MATCH_DETAILS.format(APIKEY, match_id)).json()['result']
            return j['start_time'] + j['duration']
        except Exception as e:
            print(e)
            return -1

    def request_match(self, match_id):
        try:
            j = requests.post(OPENDOTA_REQUEST.format(match_id)).json()
            print('{} 比赛编号{} 开始请求分析'.format(datetime.now(), match_id))
            job_id = j['job']['jobId']
            while j:
                time.sleep(2)
                j = requests.get(OPENDOTA_REQUEST.format(job_id)).json()
            print('{} 比赛编号{} 分析完成'.format(datetime.now(), match_id))
            return True
        except Exception as e:
            print(e)
            return False

    def get_match(self, match_id):
        MATCH = os.path.join(DOTA2_MATCHES, f'{match_id}.json')
        if os.path.exists(MATCH):
            print('{} 比赛编号{} 读取本地保存的分析结果'.format(datetime.now(), match_id))
            return loadjson(MATCH)
        if not self.request_match(match_id):
            return {}
        match = requests.get(OPENDOTA_MATCHES.format(match_id)).json()
        if match['players'][0]['damage_inflictor_received'] is None:
            return {}
        dumpjson(match, MATCH)
        return match


    def generate_match_message(self, match_id, players):
        match = self.get_match(match_id)
        if not match:
            return None
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
                    i['damage_received'] = sum(j['damage_inflictor_received'].values())
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
        team_damage_received = 0
        team_kills = 0
        team_deaths = 0
        for i in match['players']:
            if self.get_team_by_slot(i['player_slot']) == team:
                team_damage += i['hero_damage']
                team_damage_received += sum(i['damage_inflictor_received'].values())
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
            damage_received = i['damage_received']
            kills, deaths, assists = i['dota2_kill'], i['dota2_death'], i['dota2_assist']
            gpm, xpm = i['gpm'], i['xpm']

            damage_rate = 0 if team_damage == 0 else (100 * (float(damage) / team_damage))
            damage_received_rate = 0 if team_damage_received == 0 else (100 * (float(damage_received) / team_damage_received))
            participation = 0 if team_kills == 0 else (100 * float(kills + assists) / team_kills)
            deaths_rate = 0 if team_deaths == 0 else (100 * float(deaths) / team_deaths)

            tosend.append(
                '{}使用{}, KDA: {:.2f}[{}/{}/{}], GPM/XPM: {}/{}, ' \
                '补刀数: {}, 总伤害: {}({:.2f}%), 承受伤害: {}({:.2f}%), ' \
                '参战率: {:.2f}%, 参葬率: {:.2f}%' \
                .format(nickname, hero, kda, kills, deaths, assists, gpm, xpm, last_hits,
                        damage, damage_rate, damage_received, damage_received_rate,
                        participation, deaths_rate)
            )

        return '\n'.join(tosend)

    def generate_match_image(self, match_id):
        match = self.get_match(match_id)
        image = Image.new('RGB', (800, 800), (255, 255, 255))
        font = ImageFont.truetype(os.path.expanduser('~/.kusa/MSYH.TTC'), 12)
        font2 = ImageFont.truetype(os.path.expanduser('~/.kusa/MSYH.TTC'), 18)
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 800, 100), 'black')
        title = '比赛 ' + str(match['match_id'])
        title_size = font2.getsize(title)
        draw.text(((800 - title_size[0]) / 2, 10), title, font=font2, fill=(255, 255, 255))
        # 手动加粗
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
        level = SKILL_LEVEL[match['skill']] if match.get('skill') else 'Unknown'
        region_id = 'region_{}'.format(match.get('region'))
        region = REGION[region_id] if region_id in REGION else '未知'
        mode_id = match["game_mode"]
        mode = GAME_MODE[mode_id] if mode_id in GAME_MODE else '未知'
        lobby_id = match['lobby_type']
        lobby = LOBBY[lobby_id] if lobby_id in LOBBY else '未知'
        draw.text((20, 70), start_time, font=font, fill=(255, 255, 255))
        draw.text((200, 70), duration, font=font, fill=(255, 255, 255))
        draw.text((360, 70), level, font=font, fill=(255, 255, 255))
        draw.text((500, 70), region, font=font, fill=(255, 255, 255))
        draw.text((650, 70), f'{mode}/{lobby}', font=font, fill=(255, 255, 255))
        for slot in range(0, 2):
            draw.text(
                    (20, 120 + slot * 300),
                    SLOT_CHINESE[slot],
                    font=font,
                    fill=(192, 0, 0)
                )
            for i in range(0, 5):
                idx = slot * 5 + i
                p = match['players'][idx]
                hero_head = Image.open(os.path.join(IMAGES, '{}_full.png'.format(HEROES[p['hero_id']])))
                hero_head = hero_head.resize((80, 45), Image.ANTIALIAS)
                image.paste(hero_head, (20, 150 + slot * 50 + idx * 50))
                draw.text(
                    (120, 150 + slot * 50 + idx * 50),
                    p.get('personaname') if p.get('personaname') else '匿名',
                    font=font,
                    fill=(0, 0, 0)
                )
                kda = '{}/{}/{}\nKDA:{:.2f}'.format(
                    p['kills'], p['deaths'], p['assists'],
                    (p['kills'] + p['assists']) if p['deaths'] == 0 else (p['kills'] + p['assists']) / p['deaths']
                )
                draw.text(
                    (300, 150 + slot * 50 + idx * 50),
                    kda,
                    font=font,
                    fill=(0, 0, 0)
                )

                s = 1 if 'ultimate_scepter' in p['item_usage'] else 0
                scepter_img = Image.open(os.path.join(IMAGES, f'scepter_{s}.png'))
                scepter_img = scepter_img.resize((20, 20), Image.ANTIALIAS)
                image.paste(scepter_img, (420 , 150 + slot * 50 + idx * 50))
                s = 1 if 'aghanims_shard' in p['item_usage'] else 0
                shard_img = Image.open(os.path.join(IMAGES, f'shard_{s}.png'))
                shard_img = shard_img.resize((20, 11), Image.ANTIALIAS)
                image.paste(shard_img, (420 , 170 + slot * 50 + idx * 50))

                for item in ITEM_SLOTS:
                    if p[item] == 0:
                        continue
                    item_img = Image.open(os.path.join(IMAGES, '{}_lg.png'.format(ITEMS[p[item]])))
                    item_img = item_img.resize((42, 31), Image.ANTIALIAS)
                    item_neutral_offset = 20 if item == 'item_neutral' else 0
                    image.paste(item_img,(470 + item_neutral_offset + 42 * ITEM_SLOTS.index(item), 150 + slot * 50 + idx * 50))
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
        for match_id in steamdata['DOTA2_matches_pool'].keys():
            steamdata['DOTA2_matches_pool'][match_id]['end_time'] = self.get_match_end_time(match_id)
            now = int(datetime.now().timestamp())
            if steamdata['DOTA2_matches_pool'][match_id]['end_time'] <= now - 86400 * 7:
                todelete.append(match_id)
                continue
            if steamdata['DOTA2_matches_pool'][match_id]['end_time'] >= now - 600:
                continue
            m = self.generate_match_message(
                match_id=match_id,
                players=steamdata['DOTA2_matches_pool'][match_id]['players']
            )
            if isinstance(m, str):
                self.generate_match_image(match_id=match_id)
                m += '\n[CQ:image,file=file:///{}]'.format(os.path.join(DOTA2_MATCHES, f'{match_id}.png'))
                reports.append(
                    {
                        'message': m,
                        'user'   : [p['uid'] for p in steamdata['DOTA2_matches_pool'][match_id]['players']]
                    }
                )
                todelete.append(match_id)
        for match_id in todelete:
            del steamdata['DOTA2_matches_pool'][match_id]
        dumpjson(steamdata, STEAM)
        return reports