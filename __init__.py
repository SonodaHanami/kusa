import os
import json
from .utils import *

__all__ = [
    'Kusa',
]

default_config = {
    'ADMIN': 0,
    'BOT': 0,
    'SETU_APIKEY': '',
}

config_path = os.path.join(
    os.path.abspath(os.path.dirname(__file__)),
    'config.json'
)
if not os.path.exists(config_path):
    dumpjson(default_config, config_path)

from .kusa import Kusa
