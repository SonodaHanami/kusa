import os
import json
from .utils import *

__all__ = [
    'kusa',
]

default_config = {
    'ADMIN': '',
    'BOT': '',
    'SETU_APIKEY': '',
    'STEAM_APIKEY': '',
}

config_path = os.path.join(
    os.path.abspath(os.path.dirname(__file__)),
    'config.json'
)
if not os.path.exists(config_path):
    dumpjson(default_config, config_path)

mkdir_if_not_exists(os.path.expanduser('~/.kusa'))
mkdir_if_not_exists(os.path.expanduser('~/.kusa/fonts'))
mkdir_if_not_exists(os.path.expanduser('~/.kusa/images'))

from .kusa import Kusa
