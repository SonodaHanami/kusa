import os
import json


def loadjson(jsonfile, default={}):
    try:
        data = json.load(open(jsonfile, 'r'))
    except:
        data = default
    finally:
        return data

def dumpjson(jsondata, jsonfile):
    with open(jsonfile, 'w') as f:
        json.dump(jsondata, f, ensure_ascii=False, indent=4)

def load_config():
    return loadjson(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'config.json'))