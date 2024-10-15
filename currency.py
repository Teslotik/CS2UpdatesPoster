import json
import os
import re
import sys
import traceback
from time import sleep
import requests
import telebot

from config import Config
import templates

cfg = Config.load('config.yaml')
bot = telebot.TeleBot(cfg.tg_token)

while True:
    try:
        # Запрашиваем курс валюты
        r = requests.get(r'https://api.steam-currency.ru/currency')
        assert r.status_code == 200, 'Failed to retrive currency site'
        
        # Парсим
        usd = next(iter(r.json().get('data', [])), {}).get('close_price', None)
        assert usd is not None, 'Failed to parse currency'

        # Постим
        bot.send_message(cfg.tg_channel, message_thread_id = cfg.tg_thread, text = templates.currency.format(
            USD = usd
        ))
        print('Currency:', usd)
        
        # sleep(10)
        sleep(24 * 60 * 60)
    except Exception as e:
        print('Currency bot crashed, restarting in 5 mins...')
        traceback.print_exc()
        sleep(5 * 60)