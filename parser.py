import datetime
import itertools
import json
import re
import aiohttp
from aiohttp import ClientSession
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import asyncio

def contains_email(text):
    email_regex = r'[\w\.-]+@[\w\.-]+'
    return re.search(email_regex, text) is not None
# ...

async def fetch(session, url):
    async with session.get(url) as response:
        return await response.json()

async def get_channel_links(youtube, keyword, max_results):
    async with youtube.search().list(
        part='snippet',
        q=keyword,
        type='channel',
        maxResults=max_results
    ) as request:
        response = await request.execute()
        return [f"https://www.youtube.com/channel/{item['snippet']['channelId']}" for item in response['items']]

async def get_channel_info(youtube, channel_id):
    async with youtube.channels().list(
        part="snippet,statistics",
        id=channel_id
    ) as request:
        response = await request.execute()
        if not response.get('items'):
            return None, None, None, None, None
        subscriber_count = int(response['items'][0]['statistics'].get('subscriberCount', 0))
        view_count = int(response['items'][0]['statistics'].get('viewCount', 0))
        created_at = datetime.datetime.strptime(response['items'][0]['snippet']['publishedAt'].rstrip('Z').split('.')[0], "%Y-%m-%dT%H:%M:%S").date()
        country = response['items'][0]['snippet'].get('country', 'Unknown')
        description = response['items'][0]['snippet'].get('description', '')
        return subscriber_count, view_count, created_at, country, description

async def get_latest_video_info(youtube, channel_id):
    async with youtube.search().list(
        part="snippet",
        channelId=channel_id,
        maxResults=1,
        order="date"
    ) as request:
        response = await request.execute()
        if not response.get('items'):
            return None, None
        latest_video_date = datetime.datetime.strptime(response['items'][0]['snippet']['publishedAt'].rstrip('Z').split('.')[0], "%Y-%m-%dT%H:%M:%S").date()
        video_description = response['items'][0]['snippet'].get('description', '')
        return latest_video_date.strftime("%d.%m.%Y"), video_description

async def process_api_key(api_key, keywords, used_keywords, config, lang, min_subs, max_subs):
    youtube = build('youtube', 'v3', developerKey=api_key)
    existing_links = set(read_from_file('database/data.txt'))
    total_links = set()

    try:
        with open("database/data.txt", "r") as db_file:
            total_links = set(line.strip() for line in db_file)
    except FileNotFoundError:
        pass

    for keyword in keywords:
        if keyword in used_keywords:
            continue

        print(f"Using keyword: {keyword}")
        try:
            channel_links = await get_channel_links(youtube, keyword, max_results)
            for link in channel_links:
                if link in total_links:
                    continue

                total_links.add(link)

                with open("database/data.txt", "a") as db_file:
                    db_file.write(link + "\n")

                channel_id = link.split('/')[-1]
                subs_count, view_count, created_at, country, channel_description = await get_channel_info(youtube, channel_id)
                if subs_count is None:
                    continue
                if config['GeoWhitelist'] and country not in config['Whitelist']:
                    continue
                if config['GeoBlacklist'] and country in config['Blacklist']:
                    continue
                if min_subs <= subs_count <= max_subs:
                    latest_video_date, video_description = await get_latest_video_info(youtube, channel_id)

                    if config['VIPmode'] and (contains_email(channel_description) or contains_email(video_description)):
                        continue

                    info_line = format_info_line(config, link, subs_count, view_count, created_at, country, latest_video_date)
                    print(info_line)

                    with open("links.txt", "a", encoding='utf-8') as file:
                        file.write(info_line + "\n")

                    with open("just-links.txt", "a") as file:
                        file.write(link + "\n")

        except HttpError as error:
            if 'quota' in str(error):
                print(messages[lang]['quota_error'].format(api_key=api_key))
                break
            elif 'suspended' in str(error):
                print(f"API Key {api_key} is suspended, it will be skipped.")
                break
            else:
                print(f"An error occurred: {error}")
                break
        finally:
            # Независимо от результата, добавляем использованное ключевое слово в множество
            used_keywords.add(keyword)
            # Сохраняем обновленный список использованных ключевых слов в файл
            save_used_keywords("used_keywords.txt", used_keywords)

async def main():
    api_keys = get_api_keys('api.txt')
    keywords = get_keywords('keys.txt')
    max_results = 50
    min_subs = int(input(messages[lang]['input_min']))
    max_subs = int(input(messages[lang]['input_max']))

    # Загрузите список использованных ключевых слов из файла (если он существует)
    used_keywords = load_used_keywords("database/used_keywords.txt")

    tasks = []
    async with ClientSession() as session:
        for api_key in api_keys:
            task = asyncio.ensure_future(process_api_key(api_key, keywords, used_keywords, config, lang, min_subs, max_subs))
            tasks.append(task)

        await asyncio.gather(*tasks)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())