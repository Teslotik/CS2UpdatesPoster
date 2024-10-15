import re
from typing import List, Dict, Tuple
from types import LambdaType
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import traceback
from time import sleep

# Steam wiki форматирование
# https://steamcommunity.com/comment/Announcement/formattinghelp?ysclid=lxvk3y4ne5480666845
# [h1] Заголовок [/h1]
# [h2] Заголовок [/h2]
# [h3] Заголовок [/h3]
# [b] Полужирный текст [/b]Полужирный текст
# [u] Подчёркнутый текст [/u]Подчёркнутый текст
# [i] Курсив [/i]Курсив
# [strike] Зачёркнутый текст [/strike]Зачёркнутый текст
# [spoiler] Скрытый текст [/spoiler]
# [noparse] Не обрабатывать [b]теги[/b] [/noparse]Не обрабатывать [b]теги[/b]
# [hr][/hr]Нарисовать горизонтальную линию
# [url=store.steampowered.com] Ссылка [/url]
tags = {
    '\\n':      r'(\n)',           # Новая строка
    'h1':       r'(\[h1\])',        # Заголовок
    '/h1':      r'(\[/h1\])',
    'h2':       r'(\[h2\])',        # Заголовок
    '/h2':      r'(\[/h2\])',
    'h3':       r'(\[h3\])',        # Заголовок
    '/h3':      r'(\[/h3\])',
    'b':        r'(\[b\])',         # Полужирный текст
    '/b':       r'(\[/b\])',
    'u':        r'(\[u\])',         # Подчёркнутый текст
    '/u':       r'(\[/u\])',
    'i':        r'(\[i\])',         # Курсив
    '/i':       r'(\[/i\])',
    'strike':   r'(\[strike\])',    # Зачёркнутый текст
    '/strike':  r'(\[/strike\])',
    'spoiler':  r'(\[spoiler\])',   # Скрытый текст
    '/spoiler': r'(\[/spoiler\])',
    'noparse':  r'(\[noparse\])',   # Не обрабатывать
    '/noparse': r'(\[/noparse\])',
    'hr':       r'(\[hr\])',        # Нарисовать горизонтальную линию
    '/hr':      r'(\[/hr\])',
    'url':      r'(\[url=.*?\])',   # Ссылка
    '/url':     r'(\[/url\])',
    'list':     r'(\[list\])',      # Список
    '/list':    r'(\[/list\])',
    '*':        r'(\[\*\])'          # Пункт
}

log = 'log.txt'
def suppress(delay = None, retries = 1):
    def decorator(func):
        '''Игнорирует все исключения'''
        def wrapper(*args, **kwargs):
            for i in range(retries):
                try:
                    return func(*args, **kwargs)
                except Exception as exception:
                    print(f'Function failed: {func.__name__}', args, kwargs)
                    print(f'Retry: {i + 1}/{retries}')
                    print(exception)
                    traceback.print_exc()
                    with open(log, 'a', encoding = 'utf-8') as file:
                        file.write('{}/{} {} {}\n'.format(
                            i + 1, retries,
                            str(datetime.now()),
                            traceback.format_exc())
                        )
                    if isinstance(delay, (int, float)): sleep(delay)
        return wrapper
    return decorator


def tokenize(text:str, tokens:List[Tuple[str]]) -> List[str]:
    '''Рекурсивно делит строку по токенам с сохранением самих токенов'''
    (label, token), *tokens = tokens
    items = [i for i in re.split(token, text) if i != '']

    if not tokens: return items

    result = []
    for item in items:
        if item == token:
            # NOTE предположительно нерабочая и ненужная ветка
            result.append(item)
        else:
            result.extend(tokenize(item, tokens))
    return result

# VK printer
def printer(callback:LambdaType, text:str):
    text = tokenize(text, tags.items())
    stack = []
    for i, item in enumerate(text):
        tag = next((k for (k, v) in tags.items() if re.fullmatch(v, item)), None)
        if tag is None:
            # Plain text
            callback(translate(item))
            continue

        closed = tag.startswith('/')
        if tag == '\\n':
            callback('\n')
        if tag == 'url':
            callback(' ')
        elif tag == '/url':
            url = text[i - 2].replace('[url=', '').replace(']', '').replace('\\/', '/')
            callback(f' {url} ')
        elif tag == '*':
            callback('' * stack.count('list') + '- ')
        elif closed:
            stack.pop()
        elif not closed:
            stack.append(tag)
        else:
            # Unknown
            callback(item)

@suppress(delay = 60, retries = 3)
def translate(text:str):
    with open('whitelist.txt', 'r', encoding = 'utf-8') as file:
        exclude = file.read().split('\n')
    
    for word in exclude:
        if word == '': continue
        # We decorate whitelisted strings so translation will not affect
        text = text.replace(word, f"KCSP{word.replace(' ', 'WCSE')}KCSP")

    r = requests.get(
        'https://translate.google.com/m',
        params = {
            'tl': 'ru',
            'sl': 'en',
            'q': text
        }
    )
    soup = BeautifulSoup(r.text, 'lxml')
    return soup.find('div', class_ = 'result-container').text.replace('KCSP', '').replace('WCSE', ' ')