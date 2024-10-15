import asyncio
import json
import os
import re
import sys
import time
import webbrowser
from collections import deque
from io import BytesIO

import discord as dis
import requests
import telebot
from furl import furl
from PIL import Image, ImageDraw, ImageFont, ImageColor

import templates
from algorithm import *
from config import Config

# ------------------------------ Утилиты ------------------------------

class Slot:
    def __init__(self, callback, **kwargs):
        self.callback = callback
        self.kwargs = kwargs

# ------------------------------ Конфиг ------------------------------

cfg = Config.load('config.yaml')

# ------------------------------ Приложения ------------------------------

class Application:
    def __init__(self):
        self.slots = {}
        print("Application created")

    # TODO заменить continue на yield
    # TODO задержка определяется не здесь, а обработчике генератора
    def run(self):
        print("Application started")
        last = None
        while True:
            # Получаем json с постами (событиями)
            @suppress(delay = cfg.checkout_interval, retries = 3)
            def query():
                r = requests.get(cfg.csgo_site)
                assert r.status_code == 200, f'Failed to retrive update from CS:GO site {r.status_code}, {r.text}'
                return r.json()
            source = query()
            if source is None: continue

            # Получаем версию
            @suppress(delay = cfg.checkout_interval, retries = 3)
            def query_update():
                r = requests.get('https://api.steampowered.com/ISteamApps/UpToDateCheck/v1/', params = {'appid': 730, 'version': 0})
                assert r.status_code == 200, f'Failed to retrive version from steam api {r.status_code}, {r.text}'
                return r.json()
            update = query_update()
            if update is None: continue

            # LEGACY
            # Тест - загружаем сайт из файла
            # source = None
            # with open('H:/Projects/CsGoUpdates/test/web.html', 'r', encoding = 'utf-8') as file:
            #     source = file.read()

            # Парсим страничку CS:GO updates и версию
            @suppress(delay = cfg.checkout_interval)
            def parse():
                events = source.get('events')
                while events:
                    # Парсим все посты
                    event, *events = events             # берём последний пост
                    body = event.get('announcement_body', {})
                    # Парсим последний пост
                    title = body.get('headline', 'Обновление')
                    date = time.gmtime(event.get('rtime32_start_time', 946684800)) # 1 января 2000 года 0:00:00
                    text = body.get('body', 'Дополнительной информации об обновлении нет')
                    tags = body.get('tags', [])
                    if 'patchnotes' not in tags: continue
                    v = str(update.get('response', {}).get('required_version', -1))
                    version = f'{v[:1]}.{v[1:3]}.{v[3:4]}.{v[4:]}'
                    result = []
                    printer(lambda text: result.append(text), text)
                    return title, date, ''.join(result), date.tm_mday, date.tm_mon, date.tm_year, version

            data = parse()
            if data is None: continue
            title, date, text, day, month, year, version = data

            # Пропускаем итерацию, если новый пост не найден или последний пост не нужно добавлять
            if last is None and cfg.upload_last == False:
                print('Detected new post, skipping first time (see config for details)', title)
            if (last is not None and last == title) or (last is None and cfg.upload_last == False):
                last = title
                sleep(cfg.checkout_interval)
                continue
            print('Detected new post dispatching:', title)
            last = title

            # Рассылаем данные постерам (vk, discord, telegram, ...)
            self.emit(
                'SendEvent',
                title = title,
                date = date,
                text = text,
                day = '{:02d}'.format(day),
                month = '{:02d}'.format(month),
                year = f'{year}'
            )
            print('Done')

    def subscribe(self, event: str, callback, **kwargs):
        slots = self.slots.get(event, [])
        slots.append(Slot(callback, **kwargs))
        self.slots.update({event: slots})
        return self
    
    def emit(self, event: str, **kwargs):
        for slot in self.slots.get(event, []):
            kwargs = kwargs.copy()
            kwargs.update(slot.kwargs)
            slot.callback(self, **kwargs)
    
    # Фабричные методы

    # Callback'и


# TODO
class ConsoleApplication(Application):
    def __init__(self):
        super().__init__()
        if cfg.vk_owner is None: cfg.vk_owner = int(input('Идентификатор сообщества или пользователя: '))
        if cfg.vk_app is None: cfg.vk_app = int(input('Идентификатор приложения/бота: '))
        if cfg.vk_token is None:
            webbrowser.open(
                furl(cfg.vk_auth).add({
                    'client_id': cfg.vk_app,
                    'redirect_uri': 'https://api.vk.com/blank.html',
                    'display': 'page',
                    'scope': 'wall,offline,stories,photos',
                    'response_type': 'token',
                    'v': cfg.vk_version,
                }).url
            )
            cfg.vk_token = input('Токен доступа к api ВК: ')
        if cfg.checkout_interval is None: cfg.checkout_interval = int(input('Интервал проверки обновлений (в секундах): '))
        if cfg.vk_photo is None: cfg.vk_photo = int(input('Изображение: '))
        if cfg.upload_last is None: cfg.upload_last = input('Загрузить последний пост? (yes/no): ') == 'yes'
        cfg.save()


# TODO
# ... or replace with Flet or Reflex
class QtApplication(Application):
    def __inti__(self):
        super().__init__()

# ------------------------------ Стратегии коммитов ------------------------------

@suppress()
def vk(app: Application, template, title, date, text, day, month, year, **kwargs):
    # ? Проверяем - загружена ли уже запись

    # Текст поста
    message = template.format(
        title = title,
        date = date,
        text = text[:1500],
        day = day,
        month = month,
        year = year
    )

    # ------------------------------ Создаём запись на стене ------------------------------
    # Получаем сервер загрузки изображения для поста
    r = requests.post(f'{cfg.vk_api}/method/photos.getUploadServer', params = {
        'album_id': cfg.vk_album_id,
        'group_id': abs(cfg.vk_owner),
        'access_token': cfg.vk_token,
        'v': cfg.vk_version
    })
    # print(r.text)
    assert r.status_code == 200, f'VK messages get upload server http request failed {r.status_code}, {r.text}'
    album_id = r.json().get('response', {}).get('album_id')
    upload_url = r.json().get('response', {}).get('upload_url')
    assert album_id and upload_url, 'Failed to get VK messages uplodad server'

    # Загружаем изображение истории на сервер
    with Image.open('UpdateCS2_2023_.png') as image:
        draw = ImageDraw.Draw(image)
        draw.text(xy = (1599 // 2, 428), anchor = 'mm', fill = (30, 32, 47),
            text = f'{day}.{month}.{year}',
            font = ImageFont.truetype('High_Speed.ttf', size = 152)
        )
        stream = BytesIO()
        image.save(stream, format = 'PNG')
        r = requests.post(upload_url, files = {
                'photo': ('UpdateCS2_2023_.png', stream.getvalue(), 'image/jpeg')
            }
        )
        # print(r.text)
        assert r.status_code == 200, f'Failed to upload image to the VK messages server {r.status_code}, {r.text}'
        server = r.json().get('server')
        photos_list = r.json().get('photos_list')
        hash = r.json().get('hash')
        assert all([server, photos_list, hash]), 'Failed to get server, photo, hash result'

    # Сохраняем изображение
    r = requests.post(f'{cfg.vk_api}/method/photos.save', params = {
        'album_id': cfg.vk_album_id,
        'group_id': abs(cfg.vk_owner),
        'photos_list': photos_list,
        'server': server,
        'hash': hash,
        'access_token': cfg.vk_token,
        'v': cfg.vk_version
    })
    # print(r.text)
    assert r.status_code == 200, f'VK save photo http request failed {r.status_code}, {r.text}'
    attachment = next(iter(r.json().get('response', [])), {})
    media_id = attachment.get('id')
    owner_id = attachment.get('owner_id')
    assert media_id and owner_id, 'Photo was not saved on the VK server'

    # Создаём запись на стене
    @suppress(delay = cfg.checkout_interval, retries = 3)
    def query():
        r = requests.post(f'{cfg.vk_api}/method/wall.post', params = {
            'owner_id': cfg.vk_owner,
            'from_group': 1,
            'message': message,
            'attachments': f'photo{owner_id}_{media_id}',
            'access_token': cfg.vk_token,
            'v': cfg.vk_version
        })
        # print(r.text)
        assert r.status_code == 200, f'Post HTTP request failed {r.status_code}, {r.url}, {r.text}'
        response = r.json().get('response')
        assert response is not None, 'Failed to post message on the wall'
        return response
    response = query()

    # Парсим ответ
    post_id = response.get('post_id')

    # ------------------------------ Добавляем комментарий к записи на стене ------------------------------
    r = requests.post(f'{cfg.vk_api}/method/wall.createComment', params = {
        'owner_id': cfg.vk_owner,
        'post_id': post_id,
        'from_group': abs(cfg.vk_owner),
        'message': 'Пост создан автоматически',
        'access_token': cfg.vk_token,
        'v': cfg.vk_version
    })
    # print(r.text)
    assert r.status_code == 200, f'Create comment http request failed {r.status_code}, {r.text}'
    response = r.json().get('response')
    assert response is not None, 'Failed to create comment in the wall post'

    # ------------------------------ Создаём историю ------------------------------
    # Получаем сервер загрузки изображения для истории
    r = requests.post(f'{cfg.vk_api}/method/stories.getPhotoUploadServer', params = {
        'add_to_news': 1,
        'link_text': 'go_to',
        'link_url': 'https://vk.com/csgoupdate',
        'group_id': abs(cfg.vk_owner),
        'access_token': cfg.vk_token,
        'v': cfg.vk_version
    })
    # print(r.text)
    assert r.status_code == 200, f'VK stories get upload server http request failed {r.status_code}, {r.text}'
    url = r.json().get('response', {}).get('upload_url')
    assert url is not None, 'Failed to get VK stories uplodad server'

    # Загружаем изображение истории на сервер
    with open('vk_story.jpg', 'rb') as file:
        r = requests.post(url, files = {
                'file': file
            }
        )
        # print(r.text)
        assert r.status_code == 200, f'Failed to upload image to the VK stories server {r.status_code}, {r.text}'
        upload_result = r.json().get('response', {}).get('upload_result')
        assert upload_result is not None, 'Failed to get upload result'
    
    # Сохраняем историю
    r = requests.post(f'{cfg.vk_api}/method/stories.save', params = {
        'upload_results': upload_result,
        'access_token': cfg.vk_token,
        'v': cfg.vk_version
    })
    # print(r.text)
    assert r.status_code == 200, f'VK save story http request failed {r.status_code}, {r.text}'
    response = r.json().get('response')
    assert response, 'Story was not saved on the VK server'



@suppress()
def console(app: Application, template, title, date, text, day, month, year, **kwargs):
    # Текст поста
    message = template.format(
        title = title,
        date = date,
        text = text,
        day = day,
        month = month,
        year = year
    )
    print(message)


bot = telebot.TeleBot(cfg.tg_token)
@suppress()
def telegram(app: Application, template, title, date, text, day, month, year, **kwargs):
    bot.send_message(cfg.tg_channel, message_thread_id = cfg.tg_thread, text = template.format(
        title = title,
        date = date,
        text = text[:3050],
        day = day,
        month = month,
        year = year
    ))
    # with open('src/image.jpg', 'rb') as photo:
    #     bot.send_photo(cfg.tg_channel, message_thread_id = cfg.tg_thread, photo = photo)

@suppress()
def discord(app: Application, template, title, date, text, day, month, year, **kwargs):
    async def send():
        intents = dis.Intents.none()
        client = dis.Client(intents = intents)
        await client.login(cfg.ds_token)

        channel = await client.fetch_channel(cfg.ds_channel)
        await channel.send(template.format(
            title = title,
            date = date,
            text = text[:1850],
            day = day,
            month = month,
            year = year
        ), file = dis.File('src/image.jpg'))

        await client.close()

    loop = asyncio.new_event_loop()
    task = loop.create_task(send())
    loop.run_until_complete(task)

# ------------------------------ ------------------------------







app = ConsoleApplication()

app.subscribe('SendEvent', vk, template = templates.common)
app.subscribe('SendEvent', telegram, template = templates.common)
# app.subscribe('SendEvent', discord, template = templates.common)
# app.subscribe('SendEvent', console, template = templates.common)    ##

app.run()

















# Запрос токена
exit(0)
a = webbrowser.open(
    furl(cfg.vk_auth).add({
        'client_id': -1,    # TODO указать
        'redirect_uri': 'https://api.vk.com/blank.html',
        'display': 'page',
        'scope': 'wall,offline,stories,photos',
        'response_type': 'token',
        'v': cfg.vk_version,
    }).url
)
print(a)