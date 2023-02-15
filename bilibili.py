import aiohttp
import json
import os
import re
import requests
import urllib.parse
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
from time import localtime, strftime
from .utils import *

logger = get_logger('kusa')

BILIBILI = os.path.expanduser("~/.kusa/bilibili.json")
BANGUMI_API = 'http://bangumi.bilibili.com/web_api/timeline_global'
MAX_RETRIES = 5

DEFAULT_DATA = {
    'bangumi_subscribe_groups': [],
    'timeline': [],
}

# 处理超过一万的数字
def handle_num(num):
    if num > 10000:
        num = f"{num / 10000:.2f}万"
    return num

def handle_image_url(url):
    return f'[CQ:image,file={url}]'

class Bangumi:
    def __init__(self, **kwargs):
        logger.info('初始化Bangumi')

        self.api = kwargs['bot_api']

        if not os.path.exists(BILIBILI):
            dumpjson(DEFAULT_DATA, BILIBILI)

        self.get_data_update()

    async def execute_async(self, message):
        msg = message['raw_message']
        group = str(message.get("group_id", ''))
        user = str(message.get("user_id", 0))

        if msg == '订阅番剧更新':
            bilibilidata = loadjson(BILIBILI)
            if group in bilibilidata['bangumi_subscribe_groups']:
                return '本群已订阅番剧更新'
            else:
                bilibilidata['bangumi_subscribe_groups'].append(group)
                dumpjson(bilibilidata, BILIBILI)
                return '订阅番剧更新成功'

        if msg == '取消订阅番剧更新':
            bilibilidata = loadjson(BILIBILI)
            if group in bilibilidata['bangumi_subscribe_groups']:
                bilibilidata['bangumi_subscribe_groups'].remove(group)
                dumpjson(bilibilidata, BILIBILI)
                return '取消订阅番剧更新成功'
            else:
                return '本群未订阅番剧更新'

        if '什么时候更新' in msg:
            t = re.sub('什么时候更新', '', msg)
            if t == '':
                return None
            bilibilidata = loadjson(BILIBILI)
            timeline = bilibilidata['timeline']
            now = int(datetime.now().timestamp())
            for i in timeline:
                for s in i['seasons']:
                    if now > s['pub_ts']:
                        continue
                    if t in s['title']:
                        return '{} 下一集 {} 将于 {} {} 更新\n{}'.format(
                            s['title'], s['pub_index'], i['date'], s['pub_time'], s['url']
                        )
            return '我不知道'

        return None


    def jobs(self):
        trigger = CronTrigger(minute='*/5')
        job = (trigger, self.get_anime_update)
        return (job,)

    def get_data_update(self):
        res = []
        retry = 0
        while not res and retry <= MAX_RETRIES:
            try:
                res = json.loads(requests.get(BANGUMI_API).text)['result']
            except Exception as e:
                logger.warning(e)
            finally:
                retry += 1
        bilibilidata = loadjson(BILIBILI)
        bilibilidata['timeline'] = res
        dumpjson(bilibilidata, BILIBILI)


    async def get_anime_update(self):
        if datetime.now().hour == 0 and datetime.now().minute == 0:
            self.get_data_update()
        sends = []
        bilibilidata = loadjson(BILIBILI)
        groups = bilibilidata['bangumi_subscribe_groups']
        timeline = bilibilidata['timeline']
        now = int(datetime.now().timestamp())
        for i in timeline:
            delta = now - i['date_ts']
            if delta > 86400 or delta < 0:
                continue
            for s in i['seasons']:
                delta = abs(now - s['pub_ts'])
                if delta < 150:
                    if '僅限' in s['title']:
                        continue
                    msg = '{} {} {} {} 更新了!\n{}\n[CQ:image,file={}]'.format(
                        i['date'], s['pub_time'], s['title'], s['pub_index'],
                        s['url'], s['square_cover']
                    )
                    for g in groups:
                        sends.append({
                            "message_type": "group",
                            "group_id": g,
                            "message": msg
                        })

        return sends


class Analysis:
    def __init__(self, **kwargs):
        logger.info('初始化Analysis')

        # group_id : last_vurl
        self.api = kwargs['bot_api']
        self.analysis_stat = {}
        self.analysis_display_image = True
        self.analysis_display_image_list = []

    async def execute_async(self, message):
        msg = message['raw_message']
        group_id = str(message.get("group_id", ''))

        # try:
        # 提取url
        url, page, time_location = self.extract(msg)
        # 如果是小程序就去搜索标题
        if not url:
            if title := re.search(r'"desc":("[^"哔哩]+")', msg):
                vurl = await self.search_bili_by_title(title[1])
                if vurl:
                    url, page, time_location = self.extract(vurl)

        # 获取视频详细信息
        reply, vurl = "", ""
        if "view?" in url:
            reply, vurl = await self.video_detail(url, page=page, time_location=time_location)
        elif "bangumi" in url:
            reply, vurl = await self.bangumi_detail(url, time_location)
        elif "xlive" in url:
            reply, vurl = await self.live_detail(url)
        elif "article" in url:
            reply, vurl = await self.article_detail(url, page)
        elif "dynamic" in url:
            reply, vurl = await self.dynamic_detail(url)

        # 避免多个机器人解析重复推送
        if group_id:
            if group_id in self.analysis_stat and self.analysis_stat[group_id] == vurl:
                return ""
            self.analysis_stat[group_id] = vurl
        # except Exception as e:
            # reply = "execute_async Error: {}\n{}".format(type(e), str(e))
        return reply

    def extract(self, text):
        try:
            url = ""
            # 视频分p
            page = re.compile(r"([?&]|&amp;)p=\d+").search(text)
            # 视频播放定位时间
            time = re.compile(r"([?&]|&amp;)t=\d+").search(text)
            # 主站视频 av 号
            aid = re.compile(r"av\d+", re.I).search(text)
            # 主站视频 bv 号
            bvid = re.compile(r"BV([A-Za-z0-9]{10})+", re.I).search(text)
            # 番剧视频页
            epid = re.compile(r"ep\d+", re.I).search(text)
            # 番剧剧集ssid(season_id)
            ssid = re.compile(r"ss\d+", re.I).search(text)
            # 番剧详细页
            mdid = re.compile(r"md\d+", re.I).search(text)
            # 直播间
            room_id = re.compile(r"live.bilibili.com/(blanc/|h5/)?(\d+)", re.I).search(text)
            # 文章
            cvid = re.compile(
                r"(/read/(cv|mobile|native)(/|\?id=)?|^cv)(\d+)", re.I
            ).search(text)
            # 动态
            dynamic_id_type2 = re.compile(
                r"(t|m).bilibili.com/(\d+)\?(.*?)(&|&amp;)type=2", re.I
            ).search(text)
            # 动态
            dynamic_id = re.compile(r"(t|m).bilibili.com/(\d+)", re.I).search(text)
            if bvid:
                url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid[0]}"
            elif aid:
                url = f"https://api.bilibili.com/x/web-interface/view?aid={aid[0][2:]}"
            elif epid:
                url = (
                    f"https://bangumi.bilibili.com/view/web_api/season?ep_id={epid[0][2:]}"
                )
            elif ssid:
                url = f"https://bangumi.bilibili.com/view/web_api/season?season_id={ssid[0][2:]}"
            elif mdid:
                url = f"https://bangumi.bilibili.com/view/web_api/season?media_id={mdid[0][2:]}"
            elif room_id:
                url = f"https://api.live.bilibili.com/xlive/web-room/v1/index/getInfoByRoom?room_id={room_id[2]}"
            elif cvid:
                page = cvid[4]
                url = f"https://api.bilibili.com/x/article/viewinfo?id={page}&mobi_app=pc&from=web"
            elif dynamic_id_type2:
                url = f"https://api.vc.bilibili.com/dynamic_svr/v1/dynamic_svr/get_dynamic_detail?rid={dynamic_id_type2[2]}&type=2"
            elif dynamic_id:
                url = f"https://api.vc.bilibili.com/dynamic_svr/v1/dynamic_svr/get_dynamic_detail?dynamic_id={dynamic_id[2]}"
            return url, page, time
        except Exception:
            return "", None, None

    async def search_bili_by_title(self, title):
        search_url = f"https://api.bilibili.com/x/web-interface/wbi/search/all/v2?keyword={urllib.parse.quote(title)}"

        async with aiohttp.request(
            "GET", search_url, timeout=aiohttp.client.ClientTimeout(10)
        ) as resp:
            result = (await resp.json())["data"]["result"]

        for i in result:
            if i.get("result_type") != "video":
                continue
            # 只返回第一个结果
            return i["data"][0].get("arcurl")

    async def video_detail(self, url: str, **kwargs):
        try:
            async with aiohttp.request(
                "GET", url, timeout=aiohttp.client.ClientTimeout(10)
            ) as resp:
                res = (await resp.json()).get("data")
                if not res:
                    return "解析到视频被删了/稿件不可见或审核中/权限不足", url
            vurl = f"https://www.bilibili.com/video/av{res['aid']}"
            title = f"标题：{res['title']}"
            cover = (
                handle_image_url(res["pic"])
                if self.analysis_display_image or "video" in self.analysis_display_image_list
                else ""
            )
            if page := kwargs.get("page"):
                page = page[0].replace("&amp;", "&")
                p = int(page[3:])
                if p <= len(res["pages"]):
                    vurl += f"?p={p}"
                    part = res["pages"][p - 1]["part"]
                    if part != res["title"]:
                        title += f"小标题：{part}\n"
            if time_location := kwargs.get("time_location"):
                time_location = time_location[0].replace("&amp;", "&")[3:]
                if page:
                    vurl += f"&t={time_location}"
                else:
                    vurl += f"?t={time_location}"
            pubdate = strftime("%Y-%m-%d %H:%M:%S", localtime(res["pubdate"]))
            tname = f"类型：{res['tname']} | UP：{res['owner']['name']} | 日期：{pubdate}"
            stat = f"播放：{handle_num(res['stat']['view'])} | 弹幕：{handle_num(res['stat']['danmaku'])} | 收藏：{handle_num(res['stat']['favorite'])}\n"
            stat += f"点赞：{handle_num(res['stat']['like'])} | 硬币：{handle_num(res['stat']['coin'])} | 评论：{handle_num(res['stat']['reply'])}"
            desc = f"简介：{res['desc']}"
            desc_list = desc.split("\n")
            desc = "".join(i + "\n" for i in desc_list if i)
            desc_list = desc.split("\n")
            if len(desc_list) > 4:
                desc = desc_list[0] + "\n" + desc_list[1] + "\n" + desc_list[2] + "……"
            reply = '\n'.join([cover, vurl, title, tname, stat, desc])
            return reply, vurl
        except Exception as e:
            reply = "视频解析出错--Error: {}".format(type(e))
            return reply, None


    async def bangumi_detail(self, url: str, time_location: str = None):
        try:
            async with aiohttp.request(
                "GET", url, timeout=aiohttp.client.ClientTimeout(10)
            ) as resp:
                res = (await resp.json()).get("result")
                if not res:
                    return None, None
            cover = (
                handle_image_url(res["cover"])
                if self.analysis_display_image or "bangumi" in self.analysis_display_image_list
                else ""
            )
            title = f"番剧：{res['title']}\n"
            desc = f"{res['newest_ep']['desc']}\n"
            index_title = ""
            style = "".join(f"{i}," for i in res["style"])
            style = f"类型：{style[:-1]}\n"
            evaluate = f"简介：{res['evaluate']}\n"
            if "season_id" in url:
                vurl = f"https://www.bilibili.com/bangumi/play/ss{res['season_id']}"
            elif "media_id" in url:
                vurl = f"https://www.bilibili.com/bangumi/media/md{res['media_id']}"
            else:
                epid = re.compile(r"ep_id=\d+").search(url)[0][len("ep_id=") :]
                for i in res["episodes"]:
                    if str(i["ep_id"]) == epid:
                        index_title = f"标题：{i['index_title']}\n"
                        break
                vurl = f"https://www.bilibili.com/bangumi/play/ep{epid}"
            if time_location:
                time_location = time_location[0].replace("&amp;", "&")[3:]
                vurl += f"?t={time_location}"
            reply = ''.join([cover, f"{vurl}\n", title, index_title, desc, style, evaluate])
            return reply, vurl
        except Exception as e:
            reply = "番剧解析出错--Error: {}".format(type(e))
            reply += f"\n{url}"
            return reply, None


    async def live_detail(self, url: str):
        try:
            async with aiohttp.request(
                "GET", url, timeout=aiohttp.client.ClientTimeout(10)
            ) as resp:
                res = await resp.json()
                if res["code"] != 0:
                    return None, None
            res = res["data"]
            uname = res["anchor_info"]["base_info"]["uname"]
            room_id = res["room_info"]["room_id"]
            title = res["room_info"]["title"]
            cover = (
                handle_image_url(res["room_info"]["cover"])
                if self.analysis_display_image or "live" in self.analysis_display_image_list
                else ""
            )
            live_status = res["room_info"]["live_status"]
            lock_status = res["room_info"]["lock_status"]
            parent_area_name = res["room_info"]["parent_area_name"]
            area_name = res["room_info"]["area_name"]
            online = res["room_info"]["online"]
            tags = res["room_info"]["tags"]
            watched_show = res["watched_show"]["text_large"]
            vurl = f"https://live.bilibili.com/{room_id}\n"
            if lock_status:
                lock_time = res["room_info"]["lock_time"]
                lock_time = strftime("%Y-%m-%d %H:%M:%S", localtime(lock_time))
                title = f"[已封禁]直播间封禁至：{lock_time}\n"
            elif live_status == 1:
                title = f"[直播中]标题：{title}\n"
            elif live_status == 2:
                title = f"[轮播中]标题：{title}\n"
            else:
                title = f"[未开播]标题：{title}\n"
            up = f"主播：{uname}  当前分区：{parent_area_name}-{area_name}\n"
            watch = f"观看：{watched_show}  直播时的人气上一次刷新值：{handle_num(online)}\n"
            if tags:
                tags = f"标签：{tags}\n"
            if live_status:
                player = f"独立播放器：https://www.bilibili.com/blackboard/live/live-activity-player.html?enterTheRoom=0&cid={room_id}"
            else:
                player = ""
            reply = ''.join([cover, vurl, title, up, watch, tags, player])
            return reply, vurl
        except Exception as e:
            reply = "直播间解析出错--Error: {}".format(type(e))
            return reply, None


    async def article_detail(self, url: str, cvid: str):
        try:
            async with aiohttp.request(
                "GET", url, timeout=aiohttp.client.ClientTimeout(10)
            ) as resp:
                res = (await resp.json()).get("data")
                if not res:
                    return None, None
            images = (
                [handle_image_url(i) for i in res["origin_image_urls"]]
                if self.analysis_display_image or "article" in self.analysis_display_image_list
                else []
            )
            vurl = f"https://www.bilibili.com/read/cv{cvid}"
            title = f"标题：{res['title']}\n"
            up = f"作者：{res['author_name']} (https://space.bilibili.com/{res['mid']})\n"
            view = f"阅读数：{handle_num(res['stats']['view'])} "
            favorite = f"收藏数：{handle_num(res['stats']['favorite'])} "
            coin = f"硬币数：{handle_num(res['stats']['coin'])}"
            share = f"分享数：{handle_num(res['stats']['share'])} "
            like = f"点赞数：{handle_num(res['stats']['like'])} "
            dislike = f"不喜欢数：{handle_num(res['stats']['dislike'])}"
            desc = view + favorite + coin + "\n" + share + like + dislike + "\n"
            reply = list(images)
            reply.extend([title, up, desc, vurl])
            return '\n'.join(reply), vurl
        except Exception as e:
            reply = "专栏解析出错--Error: {}".format(type(e))
            return reply, None


    async def dynamic_detail(self, url: str):
        try:
            async with aiohttp.request(
                "GET", url, timeout=aiohttp.client.ClientTimeout(10)
            ) as resp:
                res = (await resp.json())["data"].get("card")
                if not res:
                    return None, None
            card = json.loads(res["card"])
            dynamic_id = res["desc"]["dynamic_id"]
            vurl = f"https://t.bilibili.com/{dynamic_id}\n"
            if not (item := card.get("item")):
                return "动态不存在文字内容", vurl
            if not (content := item.get("description")):
                content = item.get("content")
            content = content.replace("\r", "\n")
            if len(content) > 250:
                content = content[:250] + "......"
            images = (
                item.get("pictures", [])
                if self.analysis_display_image or "dynamic" in self.analysis_display_image_list
                else []
            )
            if images:
                images = [handle_image_url(i.get("img_src")) for i in images]
            else:
                pics = item.get("pictures_count")
                if pics:
                    content += f"\nPS：动态中包含{pics}张图片"
            if origin := card.get("origin"):
                jorigin = json.loads(origin)
                short_link = jorigin.get("short_link")
                if short_link:
                    content += f"\n动态包含转发视频{short_link}"
                else:
                    content += f"\n动态包含转发其他动态"
            reply = str(content)
            reply.extend(images)
            reply.append(f"\n{vurl}")
            return ''.join(reply), vurl
        except Exception as e:
            reply = "动态解析出错--Error: {}".format(type(e))
            return reply, None