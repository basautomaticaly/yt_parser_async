import datetime
import itertools
import json
import re
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


def contains_email(text):
    email_regex = r'[\w\.-]+@[\w\.-]+'
    return re.search(email_regex, text) is not None


def get_channel_links(youtube, keyword, max_results):
    request = youtube.search().list(
        part='snippet',
        q=keyword,
        type='channel',
        maxResults=max_results
    )
    response = request.execute()
    return [f"https://www.youtube.com/channel/{item['snippet']['channelId']}" for item in response['items']]


def get_channel_info(youtube, channel_id):
    request = youtube.channels().list(
        part="snippet,statistics",
        id=channel_id
    )
    response = request.execute()
    if not response.get('items'):
        return None, None, None, None, None
    subscriber_count = int(response['items'][0]['statistics'].get('subscriberCount', 0))
    view_count = int(response['items'][0]['statistics'].get('viewCount', 0))
    created_at = datetime.datetime.strptime(response['items'][0]['snippet']['publishedAt'].rstrip('Z').split('.')[0],
                                            "%Y-%m-%dT%H:%M:%S").date()
    country = response['items'][0]['snippet'].get('country', 'Unknown')
    description = response['items'][0]['snippet'].get('description', '')
    return subscriber_count, view_count, created_at, country, description


def get_latest_video_info(youtube, channel_id):
    request = youtube.search().list(
        part="snippet",
        channelId=channel_id,
        maxResults=1,
        order="date"
    )
    response = request.execute()
    if not response.get('items'):
        return None, None
    latest_video_date = datetime.datetime.strptime(
        response['items'][0]['snippet']['publishedAt'].rstrip('Z').split('.')[0], "%Y-%m-%dT%H:%M:%S").date()
    video_description = response['items'][0]['snippet'].get('description', '')
    return latest_video_date.strftime("%d.%m.%Y"), video_description


def get_api_keys(filename):
    with open(filename, 'r') as file:
        return [line.strip() for line in file]


def get_keywords(filename):
    with open(filename, 'r', encoding='utf-8') as file:
        return [line.strip() for line in file]



used_keywords = set()


def load_config(filename):
    with open(filename, 'r') as file:
        return json.load(file)


def write_to_file(filename, content, mode='a'):
    with open(filename, mode, encoding='utf-8') as file:
        file.write(content + "\n")


def read_from_file(filename):
    with open(filename, 'r', encoding='utf-8') as file:
        return [line.strip() for line in file]


def convert_count(count):
    if count >= 10 ** 6:
        return str(count // 10 ** 6) + "kk"
    elif count >= 10 ** 3:
        return str(count // 10 ** 3) + "k"
    else:
        return str(count)


def format_info_line(config, link, subs_count, view_count, created_at, country, latest_video_date):
    info_line = f"Link: {link}, Subscribers: {convert_count(subs_count)}, Channel views: {convert_count(view_count)}, Created: {created_at.strftime('%d.%m.%Y')}, Country: {country}, Last Video: {latest_video_date}"
    return info_line


def update_keywords_file(filename, keyword):
    with open(filename, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    with open(filename, 'w', encoding='utf-8') as file:
        for line in lines:
            if line.strip() != keyword:
                file.write(line)


def load_used_keywords(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            return set(line.strip() for line in file)
    except FileNotFoundError:
        return set()


def save_used_keywords(filename, keywords_set):
    with open(filename, 'w', encoding='utf-8') as file:
        for keyword in keywords_set:
            file.write(keyword + "\n")



used_keywords = load_used_keywords("database/used_keywords.txt")

messages = {
    'ua': {
        'input_min': "Введіть мінімальну кількість підписників: ",
        'input_max': "Введіть максимальну кількість підписників: ",
        'quota_error': "Ключ API {api_key} перевищив квоту, його буде пропущено.",
        'api_error': "Сталася помилка з API Key {api_key}, його буде пропущено."
    },
    'ru': {
        'input_min': "Введите минимальное количество подписчиков: ",
        'input_max': "Введите максимальное количество подписчиков: ",
        'quota_error': "Ключ API {api_key} превысил квоту, его будет пропущено.",
        'api_error': "Произошла ошибка с API Key {api_key}, он будет пропущен."
    },
    'eng': {
        'input_min': "Enter minimum subscriber count: ",
        'input_max': "Enter maximum subscriber count: ",
        'quota_error': "API Key {api_key} exceeded the quota, it will be skipped.",
        'api_error': "There was an error with API Key {api_key}, it will be skipped."
    }
}

config = load_config('config.json')
lang = config['Language']
api_keys = get_api_keys('api.txt')
keywords = get_keywords('keys.txt')
max_results = 50
min_subs = int(input(messages[lang]['input_min']))
max_subs = int(input(messages[lang]['input_max']))

existing_links = set(read_from_file('database/data.txt'))

total_links = set()
try:
    with open("database/data.txt", "r") as db_file:
        total_links = set(line.strip() for line in db_file)
except FileNotFoundError:
    pass

for api_key in api_keys:
    try:
        youtube = build('youtube', 'v3', developerKey=api_key)

        for keyword in keywords:
            if keyword in used_keywords:
                continue

            print(f"Using keyword: {keyword}")
            try:
                channel_links = get_channel_links(youtube, keyword, max_results)
                for link in channel_links:
                    if link in total_links:
                        continue

                    total_links.add(link)

                    with open("database/data.txt", "a") as db_file:
                        db_file.write(link + "\n")

                    channel_id = link.split('/')[-1]
                    subs_count, view_count, created_at, country, channel_description = get_channel_info(youtube,
                                                                                                        channel_id)
                    if subs_count is None:
                        continue
                    if config['GeoWhitelist'] and country not in config['Whitelist']:
                        continue
                    if config['GeoBlacklist'] and country in config['Blacklist']:
                        continue
                    if min_subs <= subs_count <= max_subs:
                        latest_video_date, video_description = get_latest_video_info(youtube, channel_id)

                        if config['VIPmode'] and (
                                contains_email(channel_description) or contains_email(video_description)):
                            continue

                        info_line = format_info_line(config, link, subs_count, view_count, created_at, country,
                                                     latest_video_date)
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
                used_keywords.add(keyword)
                save_used_keywords("used_keywords.txt", used_keywords)

    except HttpError:
        print(messages[lang]['api_error'].format(api_key=api_key))
