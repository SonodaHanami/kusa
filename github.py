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
githubdata = {
    repository_name_1: [
        subscribe_group_id_1,
        subscribe_group_id_2,
        ...
    ],
    repository_name_2: [...],
    ...
}
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
            repo = msg[2:].strip()
            githubdata = loadjson(GITHUB)
            if repo in githubdata:
                if group in githubdata[repo]:
                    return f'{repo}已在订阅列表中'
                else:
                    githubdata[repo].append(group)
            else:
                githubdata[repo] = [group]
            dumpjson(githubdata, GITHUB)
            self.get_commit_update()
            return f'订阅{repo}成功'

        if msg.startswith('取消订阅'):
            repo = msg[4:].strip()
            githubdata = loadjson(GITHUB)
            if repo in githubdata:
                if group in githubdata[repo]:
                    githubdata[repo].remove(group)
                    dumpjson(githubdata, GITHUB)
                    return f'取消订阅{repo}成功'
                else:
                    return f'本群未订阅{repo}'
                    githubdata[repo].append(group)
            else:
                return f'本群未订阅{repo}'
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
        githubdata = loadjson(GITHUB)

        for repo in githubdata:
            print('{}查询Github更新：{}'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), repo))
            commits = self.get_repo_commits(repo)
            if not commits:
                continue
            last = self.latest_commits.get(repo)
            self.latest_commits[repo] = commits[0]
            if last is None:
                print('Github订阅初始化：{}'.format(repo))
                continue
            if last in commits:
                idx = commits.index(last)
                commits = commits[:idx]
            updates += commits
        print('{}共查询到{}条更新'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), len(updates)))

        for repo, groups in githubdata.items():
            for commit in updates:
                if commit['repo'] == repo:
                    for group in groups:
                        news.append({
                            'group': group,
                            'msg'  : '{} {}提交了{}到{}'.format(
                                commit['time'], commit['author'], commit['msg'], commit['repo']
                            )
                        })
        news.reverse()
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