# -*- coding: utf-8 -*-
import requests
from requests import Session
from bs4 import BeautifulSoup
import urllib
import sys
import re
import os
import string
import config
import datetime

reload(sys)

login_url = 'https://www.linkedin.com/login'
post_login_url = 'https://www.linkedin.com/uas/login-submit'
course_api_url = 'https://www.linkedin.com/learning-api/detailedCourses??fields=fullCourseUnlocked,releasedOn,' \
                 'exerciseFileUrls,exerciseFiles&addParagraphsToTranscript=true&courseSlug=%s&q=slugs'
video_api_url = 'https://www.linkedin.com/learning-api/detailedCourses?addParagraphsToTranscript=false&courseSlug=%s' \
                '&q=slugs&resolution=_720&videoSlug=%s'
headers = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Accept-Language': 'en-US,en;q=0.9',
    'Connection': 'keep-alive',
    'Content-Type': 'application/x-www-form-urlencoded',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/66.0.3359.181 Safari/537.36'
}

colors = {
    'black': '\033[30m', 'red': '\033[31m', 'green': '\033[32m', 'yellow': '\033[33m', 'blue': '\033[34m',
    'magenta': '\033[95m', 'cyan': '\033[36m', 'gray': '\033[90m', 'default': '\033[39m', 'blink': '\033[5m',
}


class Lld:
    def __init__(self):
        self.session = Session()
        self.base_path = config.BASE_DOWNLOAD_PATH if config.BASE_DOWNLOAD_PATH else 'out'

    @staticmethod
    def plain_cookies(cookies):
        plain = ''
        for k, v in cookies.iteritems():
            plain += k + '=' + v + '; '
        return plain[:-2]

    @staticmethod
    def format_string(raw_string):
        replacement_dict = {u'Ä': 'Ae', u'Ö': 'Oe', u'Ü': 'Ue', u'ä': 'ae', u'ö': 'oe', u'ü': 'ue', ':': ' -'}
        invalid_chars = r'[^A-Za-z0-9\-\.\+\#]+'
        u_map = {ord(key): unicode(val) for key, val in replacement_dict.items()}
        raw_string = raw_string.translate(u_map)
        raw_string = re.sub(invalid_chars, ' ', raw_string).strip().encode('utf-8')
        i = 0
        for c in raw_string:
            if c in string.ascii_letters:
                break
            i += 1
        return raw_string[i:]

    @staticmethod
    def format_time(ms):
        seconds, milliseconds = divmod(ms, 1000)
        minitues, seconds = divmod(seconds, 60)
        hours, minitues = divmod(minitues, 60)
        return '%d:%02d:%02d,%02d' % (hours, minitues, seconds, milliseconds)

    @staticmethod
    def print_log(color, data):
        print '[' + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + ']' + \
              colors[color] + str(data) + colors['default']

    def download_file(self, url, path, file_name):
        resp = self.session.get(url, stream=True)
        if not os.path.exists(path):
            os.makedirs(path)
        try:
            with open(path + '/' + file_name, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)
        except Exception as e:
            os.remove(path + '/' + file_name)
            self.print_log('red', e)

    def download_sub(self, subs, path, file_name):
        with open(path + '/' + file_name, 'a') as f:
            i = 1
            for sub in subs:
                t_start = sub['transcriptStartAt']
                if i == len(subs):
                    t_end = t_start + 5000
                else:
                    t_end = subs[i]['transcriptStartAt']
                caption = sub['caption']
                f.write('%s\n' % str(i))
                f.write('%s --> %s\n' % (self.format_time(t_start), self.format_time(t_end)))
                f.write('%s\n\n' % caption)
                i += 1

    @staticmethod
    def download_desc(desc, course_url, path, file_name):
        if not os.path.exists(path):
            os.makedirs(path)
        with open(path + '/' + file_name, 'a') as f:
            f.write('%s\n\n%s' % (desc, course_url))

    def get_logged_session(self):
        self.print_log('cyan', '[*] Authenticating to LinkedIn')
        login_page = BeautifulSoup(self.session.get(login_url).text, 'html.parser')
        csrf = login_page.find('input', {'name': 'loginCsrfParam'})['value']
        self.print_log('cyan', '[*] Csfr token: %s' % csrf)
        login_data = urllib.urlencode(
            {'session_key': config.USERNAME, 'session_password': config.PASSWORD, 'isJsEnabled': 'false',
             'loginCsrfParam': csrf})
        headers['Cookie'] = self.plain_cookies(requests.utils.dict_from_cookiejar(self.session.cookies))
        self.session.headers.update(headers)
        resp = self.session.post(post_login_url, data=login_data, allow_redirects=True)
        if resp.status_code != 200:
            self.print_log('red', '[!] Could not authenticate to LinkedIn')
        else:
            self.print_log('cyan', '[*] Authentication successfully completed')

    def download_courses(self):
        token = self.session.cookies.get('JSESSIONID').replace('"', '')
        self.session.headers['Csrf-Token'] = token
        self.session.headers['Cookie'] = self.plain_cookies(requests.utils.dict_from_cookiejar(self.session.cookies))
        self.session.headers.pop('Accept')

        for course in config.COURSES:
            resp = self.session.get(course_api_url % course)
            course_data = resp.json()['elements'][0]
            course_name = self.format_string(course_data['title'])
            self.print_log('yellow', '[*] Starting download of course [%s]...' % course_name)
            course_path = '%s/%s' % (self.base_path, course_name)
            chapters_list = course_data['chapters']
            chapter_index = 1
            self.print_log('yellow', '[*] Parsing course\'s chapters...')
            self.print_log('yellow', '[*] %d chapters found' % len(chapters_list))
            for chapter in chapters_list:
                chapter_name = self.format_string(chapter['title'])
                self.print_log('green', '[*] --- Starting download of chapter [%s]...' % chapter_name)
                chapter_path = '%s/%s - %s' % (course_path, str(chapter_index).zfill(2), chapter_name)
                if chapter_name == '':
                    chapter_path = chapter_path[:-3]
                videos_list = chapter['videos']
                video_index = 1
                self.print_log('green', '[*] --- Parsing chapters\'s videos')
                self.print_log('green', '[*] --- %d videos found' % len(videos_list))
                for video in videos_list:
                    video_name = self.format_string(video['title'])
                    video_slug = video['slug']
                    video_path = chapter_path + '/' + '%s - %s.mp4' % (str(video_index).zfill(2), video_name)
                    if os.path.exists(video_path):
                        self.print_log('gray', '[*] ------ Skip video [%s] download '
                                               'because it already exists.' % video_name)
                        video_index += 1
                        continue
                    video_data = (self.session.get(video_api_url % (course, video_slug)))
                    try:
                        video_url = re.search('"progressiveUrl":"(.+)","streamingUrl"', video_data.text).group(1)
                    except AttributeError:
                        self.print_log('red', '[!] ------ Can\'t download the video [%s], '
                                              'probably is only for premium users' % video_name)
                        continue
                    self.print_log('magenta', '[*] ------ Downloading video [%s]' % video_name)
                    self.download_file(video_url, chapter_path, '%s - %s.mp4' % (str(video_index).zfill(2), video_name))
                    video_data = video_data.json()['elements'][0]
                    if config.SUBS:
                        try:
                            subs = video_data['selectedVideo']['transcript']['lines']
                        except KeyError:
                            self.print_log('gray', '[*] ------ No subtitles available')
                        else:
                            self.print_log('magenta', '[*] ------ Downloading subtitles')
                            self.download_sub(subs, chapter_path, '%s - %s.srt'
                                              % (str(video_index).zfill(2), video_name))
                    video_index += 1
                chapter_index += 1

            exercises_list = course_data['exerciseFiles']
            if exercises_list:
                self.print_log('gray', '[*] --- No exercise files available')
            else:
                self.print_log('green', '[*] --- Downloading exercise files')
                for exercise in exercises_list:
                    try:
                        ex_name = exercise['name']
                        ex_url = exercise['url']
                    except (KeyError, IndexError):
                        self.print_log('default', '[!] --- Can\'t download an exercise file '
                                       'for course [%s]' % course_name)
                    else:
                        self.download_file(ex_url, course_path, ex_name)
            description = course_data['description']
            self.print_log('green', '[*] --- Downloading course description')
            self.download_desc(description, 'https://www.linkedin.com/learning/%s' % course, course_path,
                               'Description.txt')


def main():
    lld = Lld()
    lld.get_logged_session()
    lld.download_courses()


if __name__ == '__main__':
    main()
