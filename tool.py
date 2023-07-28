import argparse
import logging
import os

import yaml


def load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.load(f, Loader=yaml.FullLoader)


def get_config_path():
    if os.getenv("BOT_ENGINE_CONFIG_PATH") is not None:
        return os.getenv("BOT_ENGINE_CONFIG_PATH")
    else:
        parser = argparse.ArgumentParser()
        parser.add_argument("-c", "--config", type=str, default="config.yaml")
        args = parser.parse_args()
        return args.config


def load_config():
    try:
        config_path = get_config_path()
        return load_yaml(config_path)

    except Exception as e:
        logging.error(f"load config error: {e}")
        exit(1)
