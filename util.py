import os
import json


def loadjson(jsonfile):
    return json.load(open(jsonfile, 'r'))

def dumpjson(jsondata, jsonfile):
    with open(jsonfile, 'w') as f:
        json.dump(jsondata, f, ensure_ascii=False, indent=4)

def load_config():
    return loadjson(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'config.json'))