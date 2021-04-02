import os
import json
from .kusa import Kusa

__all__ = [
    'Kusa',
]

default_config = {
    'ADMIN': 0,
    'BOT': 0,
}

config_path = os.path.join(
    os.path.abspath(os.path.dirname(__file__)),
    'config.json'
)
if not os.path.exists(config_path):
    with open(config_path, 'w') as f:
        json.dump(default_config, f, indent=4, ensure_ascii=False)
