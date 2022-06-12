import json
import os
import random
import re
import requests
from apscheduler.triggers.cron import CronTrigger
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from random import randint as ri
from .utils import *

logger = get_logger('kusa')

CONFIG = load_config()
ADMIN = CONFIG['ADMIN']

GITHUB = os.path.expanduser('~/.kusa/github.json')
COMMITS_ATOM = 'https://github.com/{}/commits.atom'

DEFAULT_DATA = {}
'''
githubdata = {
    repository_name_1: {
        'subscribe_groups': [
            subscribe_group_id_1,
            subscribe_group_id_2,
            ...
        ],
        'commits': [
            commit_hash_1,
            commit_hash_2,
            ...
        ],
    },
    repository_name_2: {
        'subscribe_groups': [...],
        'commits': [...],
    },
    ...
}
'''

class Github:
    def __init__(self, **kwargs):
        logger.info('初始化Github')

        self.api = kwargs['bot_api']

        if not os.path.exists(GITHUB):
            dumpjson(DEFAULT_DATA, GITHUB)

        self.get_all_commits_update()


    def jobs(self):
        trigger = CronTrigger(minute='*/15')
        job = (trigger, self.send_news_async)
        return (job,)


    async def execute_async(self, message):
        msg = message['raw_message']
        group = str(message.get("group_id", ''))
        user = str(message.get("user_id", 0))

        if re.match('订阅github', msg, re.I):
            repo = msg[8:].strip()
            githubdata = loadjson(GITHUB)
            first_sub = False
            if repo in githubdata:
                if group in githubdata[repo]['subscribe_groups']:
                    return f'{repo}已在订阅列表中'
                else:
                    githubdata[repo]['subscribe_groups'].append(group)
            else:
                githubdata[repo] = {
                    'subscribe_groups':[group],
                    'commits': [],
                }
                first_sub = True
            dumpjson(githubdata, GITHUB)
            if first_sub:
                self.get_commit_update(repo)
            return f'订阅{repo}成功'

        if re.match('取消订阅github', msg, re.I):
            repo = msg[10:].strip()
            githubdata = loadjson(GITHUB)
            if repo in githubdata:
                if group in githubdata[repo]['subscribe_groups']:
                    githubdata[repo]['subscribe_groups'].remove(group)
                    if len(githubdata[repo]['subscribe_groups']) == 0:
                        del githubdata[repo]
                    dumpjson(githubdata, GITHUB)
                    return f'取消订阅{repo}成功'
                else:
                    return f'本群未订阅{repo}'
            else:
                return f'本群未订阅{repo}'

        return None


    async def send_news_async(self):
        news = self.get_all_commits_update()
        for n in news:
            await self.api.send_group_msg(
                group_id=n['group'],
                message=n['msg']
            )


    def get_all_commits_update(self):
        news = []
        updates = []
        force_pushed = {}
        commit_count = 0
        githubdata = loadjson(GITHUB)

        for repo in githubdata:
            count, commits, force = self.get_commit_update(repo)
            updates += commits
            commit_count += count
            force_pushed.update(force)

        if githubdata:
            logger.info('共查询到{}个提交，其中有{}个更新'.format(commit_count, len(updates)))

        for repo, item in githubdata.items():
            for commit in updates:
                if commit['repo'] == repo:
                    for group in item['subscribe_groups']:
                        news.append({
                            'group': group,
                            'msg'  : '[{}] {}提交了{}到{}'.format(
                                commit['time'], commit['author'], commit['msg'], commit['repo']
                            )
                        })
            if force_pushed.get(repo):
                for group in item['subscribe_groups']:
                    news.append({
                        'group': group,
                        'msg'  : '[{}] {}个提交被舍弃，同时{}个新提交被强制推送'.format(
                            repo, force_pushed[repo][0], force_pushed[repo][1]
                        )
                    })
        news.reverse()
        return news


    def get_commit_update(self, repo):
        githubdata = loadjson(GITHUB)
        force = {}
        logger.info(f'查询Github更新：{repo}')
        commits = self.get_repo_commits(repo)
        count = len(commits)
        if not commits:
            return count, [], force
        last = githubdata[repo]['commits'][0] if githubdata[repo].get('commits') else None
        hashes = [c['hash'] for c in commits]
        if last is None:
            logger.info(f'Github订阅初始化：{repo}')
            githubdata[repo]['commits'] = hashes
            dumpjson(githubdata, GITHUB)
            return count, [], force
        if last in hashes:
            idx = hashes.index(last)
            commits = commits[:idx]
            githubdata[repo]['commits'] = hashes[:idx] + githubdata[repo]['commits']
        else:
            closest_commit = None
            for commit in hashes:
                if commit in githubdata[repo]['commits']:
                    closest_commit = commit
                    break
            old_index = githubdata[repo]['commits'].index(closest_commit)
            new_index = hashes.index(closest_commit)
            commits = commits[:new_index]
            githubdata[repo]['commits'] = hashes[:new_index] + githubdata[repo]['commits'][old_index:]
            force[repo] = [old_index, new_index]
        dumpjson(githubdata, GITHUB)
        return count, commits, force


    def get_repo_commits(self, repo):
        repo_url = COMMITS_ATOM.format(repo)
        r = requests.get(repo_url)
        soup = BeautifulSoup(r.text, "lxml")
        latest_commits = soup.find_all('entry')
        commits = []
        for lc in latest_commits:
            author = lc.find('author').find('name').string
            dt = datetime.strptime(lc.find('updated').string, '%Y-%m-%dT%H:%M:%SZ') + timedelta(hours=8)
            msg = lc.find('title').string.strip()
            hash = re.match('.*/(.*)', lc.find('link').get('href'))[1]
            commits.append({
                'repo'  : repo,
                'author': author,
                'hash'  : hash,
                'msg'   : msg,
                'time'  : dt,
            })
        return commits