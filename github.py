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

CONFIG = load_config()
ADMIN = CONFIG['ADMIN']

GITHUB = os.path.expanduser('~/.kusa/github.json')
'''
githubdata = [
    {
        'repo': repository_name,
        'group': group_id,
    },
    {},
    ...
]
'''
class Github:
    def __init__(self, **kwargs):
        self.api = kwargs['bot_api']

        self.latest_commits = {}

        self.get_commit_update()

    def jobs(self):
        trigger = CronTrigger(minute='*/15')
        job = (trigger, self.send_news_async)
        return (job,)


    async def execute_async(self, message):
        msg = message['raw_message']
        group = str(message.get("group_id", ''))
        user = str(message.get("user_id", 0))

        if msg.startswith('订阅'):
            repo = msg[2:]
            githubdata = loadjson(GITHUB, [])
            sub = {
                'repo': repo,
                'group': group,
            }
            if sub in githubdata:
                return f'{repo}已在订阅列表中'
            else:
                githubdata.append(sub)
            dumpjson(githubdata, GITHUB)
            return f'订阅{repo}成功'

        return None


    async def send_news_async(self):
        news = self.get_commit_update()
        for n in news:
            await self.api.send_group_msg(
                group_id=n['group'],
                message=n['msg']
            )


    def get_commit_update(self):
        news = []
        updates = []
        sub_groups = {}
        githubdata = loadjson(GITHUB, [])

        for sub in githubdata:
            if sub['repo'] in sub_groups:
                sub_groups[sub['repo']].append(sub['group'])
            else:
                sub_groups[sub['repo']] = [sub['group']]
            commits = self.get_repo_commits(sub['repo'])
            if not commits:
                continue
            last = self.latest_commits.get(sub['repo'])
            self.latest_commits[sub['repo']] = commits[0]
            if last is None:
                print('初始化{}'.format(sub['repo']))
                continue
            if last in commits:
                idx = commits.index(last)
                commits = commits[:idx]
            updates += commits
        for repo, groups in sub_groups.items():
            for commit in updates:
                if commit['repo'] == repo:
                    for group in groups:
                        news.append({
                            'group': group,
                            'msg'  : '{} {}提交了{}到{}'.format(
                                commit['time'], commit['author'], commit['msg'], commit['repo']
                            )
                        })
        return news


    def get_repo_commits(self, repo):
        repo_url = f'https://github.com/{repo}/commits/'
        r = requests.get(repo_url)
        soup = BeautifulSoup(r.text, "lxml")
        latest_authors = soup.find_all(class_='user-mention')
        commits = []
        for i in range(len(latest_authors)):
            author = latest_authors[i]
            dt = author.find_parent().find('relative-time').get('datetime')
            from datetime import datetime, timedelta
            msgs = author.find_parent('div', class_='flex-auto min-width-0').find('p', class_='mb-1').find_all('a')
            msg = ''.join([str(m.string) for m in msgs])
            commits.append({
                'repo'  : repo,
                'author': str(author.string),
                'msg'   : msg,
                'time'  : datetime.strptime(dt, '%Y-%m-%dT%H:%M:%SZ') + timedelta(hours=8),
            })
        return commits