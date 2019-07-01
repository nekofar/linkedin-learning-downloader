# -*- coding: utf-8 -*-
"""
A scraping tool that downloads video lessons from Linkedin Learning
"""

import urllib
import sys
import re
import os
import string
import datetime
import signal
import requests
from requests import Session
from requests.exceptions import ConnectionError
from bs4 import BeautifulSoup
from tqdm import tqdm
import config

reload(sys)
signal.signal(signal.SIGINT, lambda number, frame: sys.exit())

LOGIN_URL = "https://www.linkedin.com/login"
POST_LOGIN_URL = "https://www.linkedin.com/uas/login-submit"
COURSE_API_URL = (
    "https://www.linkedin.com/learning-api/detailedCourses"
    "??fields=fullCourseUnlocked,releasedOn,"
    "exerciseFileUrls,exerciseFiles&addParagraphsToTranscript=true&courseSlug={}&q=slugs"
)
VIDEO_API_URL = (
    "https://www.linkedin.com/learning-api/detailedCourses"
    "?addParagraphsToTranscript=false&courseSlug={}"
    "&q=slugs&resolution=_720&videoSlug={}"
)
SEARCH_API_URL = (
    "https://www.linkedin.com/learning-api/search"
    "?sortBy=%s&categorySlugs=List(%s)&start=0&includeLearningPaths=true&keywords=%s"
    "&count=%s&q=search&enableSpellCheck=false&entityType=COURSE"
)
HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
    "image/webp,image/apng,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Content-Type": "application/x-www-form-urlencoded",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    " (KHTML, like Gecko) Chrome/66.0.3359.181 Safari/537.36",
}

COLORS = {
    "black": "\033[30m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[95m",
    "cyan": "\033[36m",
    "gray": "\033[90m",
    "default": "\033[39m",
    "blink": "\033[5m",
}


class Lld(object):
    def __init__(self):
        self.session = Session()
        self.base_path = (
            config.BASE_DOWNLOAD_PATH if config.BASE_DOWNLOAD_PATH else "out"
        )

    @staticmethod
    def plain_cookies(cookies):
        """

        :param cookies:
        :return:
        """
        plain = ""
        for key, value in cookies.iteritems():
            plain += key + "=" + value + "; "
        return plain[:-2]

    @staticmethod
    def format_string(raw_string):
        """

        :param raw_string:
        :return:
        """
        replacement_dict = {
            u"Ä": "Ae",
            u"Ö": "Oe",
            u"Ü": "Ue",
            u"ä": "ae",
            u"ö": "oe",
            u"ü": "ue",
            ":": " -",
        }
        invalid_chars = r"[^A-Za-z0-9\-\.\+\#\']+"
        u_map = {ord(key): unicode(val) for key, val in replacement_dict.items()}
        raw_string = raw_string.translate(u_map)
        raw_string = re.sub(invalid_chars, " ", raw_string).strip().encode("utf-8")
        i = 0
        for char in raw_string:
            if char in string.ascii_letters:
                break
            i += 1
        return raw_string[i:]

    @staticmethod
    def format_time(ms):
        """

        :param ms:
        :return:
        """
        seconds, milliseconds = divmod(ms, 1000)
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return u"{:d}:{:2d}:{:2d},{:2d}".format(
            hours, minutes, seconds, milliseconds
        ).encode("utf8")

    @staticmethod
    def print_log(color, data):
        """
        Print out customized log

        :param color:
        :param data:
        """
        print u"[{}]{}{}{}".format(
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            COLORS[color],
            str(data),
            COLORS["default"],
        ).encode("utf8")

    def download_file(self, url, path, file_name):
        """

        :param url:
        :param path:
        :param file_name:
        """
        if not os.path.exists(path):
            os.makedirs(path)

        temp_file = path + "/" + file_name + ".tmp"
        main_file = path + "/" + file_name

        resp = self.session.get(url, stream=True, timeout=60)
        total = int(resp.headers["Content-Length"])

        try:
            with open(temp_file, "wb") as file_object:
                with tqdm(
                    desc=u"[{}]{}[*] ------ Downloading {:0.2f}Mb".format(
                        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        COLORS["magenta"],
                        total / 1e6,
                    ).encode("utf8"),
                    bar_format=u"{desc}: {percentage:2.0f}% | {elapsed}, {rate_fmt}".encode(
                        "utf8"
                    )
                    + (COLORS["default"]),
                    total=total,
                    ncols=100,
                    leave=False,
                    unit="b",
                    unit_scale=True,
                    unit_divisor=1e6,
                    mininterval=1
                ) as progress:
                    for chunk in resp.iter_content(chunk_size=1024):
                        if chunk:
                            file_object.write(chunk)
                            progress.update(1024)
            os.rename(temp_file, main_file)
        except ConnectionError as err:
            self.download_courses()
        except Exception as err:
            os.remove(temp_file)
            self.print_log("red", err)

    def download_sub(self, subs, path, file_name):
        """
        Download course videos subtitles

        :param subs:
        :param path:
        :param file_name:
        """
        with open(path + "/" + file_name, "a") as file_object:
            i = 1
            for sub in subs:
                t_start = sub["transcriptStartAt"]
                if i == len(subs):
                    t_end = t_start + 5000
                else:
                    t_end = subs[i]["transcriptStartAt"]
                caption = sub["caption"]
                file_object.write(u"{}\n".format(str(i)).encode("utf8"))
                file_object.write(
                    u"{} --> {}\n".format(
                        self.format_time(t_start), self.format_time(t_end)
                    ).encode("utf8")
                )
                file_object.write(u"{}\n\n".format(caption).encode("utf8"))
                i += 1

    @staticmethod
    def download_desc(desc, course_url, path, file_name):
        """
        Download course description

        :param desc:
        :param course_url:
        :param path:
        :param file_name:
        """
        if not os.path.exists(path):
            os.makedirs(path)
        with open(path + "/" + file_name, "a") as file_object:
            file_object.write(u"{}\n\n{}".format(desc, course_url).encode("utf8"))

    def download_cover(self, thumbnail, path, file_name):
        """
        Download course description

        :param thumbnail:
        :param path:
        :param file_name:
        """
        if not os.path.exists(path):
            os.makedirs(path)
        cover_path = path + "/" + file_name
        resp = self.session.get(thumbnail, stream=True)
        if resp.status_code == 200:
            with open(cover_path, "wb") as file_object:
                for chunk in resp:
                    file_object.write(chunk)

    def get_logged_session(self):
        """
        Login to the LinkedIn using login data and initialize session
        """
        self.print_log("cyan", "[*] Authenticating to LinkedIn")
        login_page = BeautifulSoup(self.session.get(LOGIN_URL).text, "html.parser")
        csrf = login_page.find("input", {"name": "loginCsrfParam"})["value"]
        self.print_log("cyan", "[*] Csfr token: {}".format(csrf))
        login_data = urllib.urlencode(
            {
                "session_key": config.USERNAME,
                "session_password": config.PASSWORD,
                "isJsEnabled": "false",
                "loginCsrfParam": csrf,
            }
        )
        HEADERS["Cookie"] = self.plain_cookies(
            requests.utils.dict_from_cookiejar(self.session.cookies)
        )
        self.session.headers.update(HEADERS)
        resp = self.session.post(POST_LOGIN_URL, data=login_data, allow_redirects=True)
        if resp.status_code != 200:
            self.print_log("red", "[!] Could not authenticate to LinkedIn")
        else:
            self.print_log("cyan", "[*] Authentication successfully completed")

    def download_courses(self):
        """
        Download courses videos and files

        """
        token = self.session.cookies.get("JSESSIONID").replace('"', "")
        self.session.headers["Csrf-Token"] = token
        self.session.headers["Cookie"] = self.plain_cookies(
            requests.utils.dict_from_cookiejar(self.session.cookies)
        )
        self.session.headers.pop("Accept")

        for course in config.COURSES:
            self.download_course(course)

    def download_course(self, course):
        """
        Download an individual course

        :param course:
        """
        resp = self.session.get(COURSE_API_URL.format(course))
        course_data = resp.json()["elements"][0]
        course_name = self.format_string(course_data["title"])
        self.print_log(
            "yellow", "[*] Starting download of course [{}]...".format(course_name)
        )
        course_path = "{}/{}".format(self.base_path, course_name)
        chapters_list = course_data["chapters"]
        chapter_index = 1
        self.print_log("yellow", "[*] Parsing course's chapters...")
        self.print_log("yellow", "[*] {:d} chapters found".format(len(chapters_list)))
        for chapter in chapters_list:
            self.download_chapter(course, chapter, course_path, chapter_index)
            chapter_index += 1

        thumbnail = course_data["webThumbnail"]
        self.print_log("green", "[*] --- Downloading course cover")
        self.download_cover(thumbnail, course_path, "Cover.jpg")

        exercises_list = course_data["exerciseFiles"]
        self.print_log("green", "[*] --- Downloading exercise files")
        self.download_exercise(exercises_list, course_name, course_path)

        description = course_data["description"]
        self.print_log("green", "[*] --- Downloading course description")
        self.download_desc(
            description,
            "https://www.linkedin.com/learning/{}".format(course),
            course_path,
            "Description.txt",
        )

    def download_chapter(self, course, chapter, course_path, chapter_index):
        """
        Download course chapter and videos
        :param course:
        :param chapter:
        :param course_path:
        :param chapter_index:
        """
        chapter_name = self.format_string(chapter["title"])
        self.print_log(
            "green", "[*] --- Starting download of chapter [{}]...".format(chapter_name)
        )
        chapter_path = "{}/{} - {}".format(
            course_path, str(chapter_index).zfill(2), chapter_name
        )
        if chapter_name == "":
            chapter_path = chapter_path[:-3]
        videos_list = chapter["videos"]
        video_index = 1
        self.print_log("green", "[*] --- Parsing chapters's videos")
        self.print_log("green", "[*] --- {:d} videos found".format(len(videos_list)))
        for video in videos_list:
            self.download_video(course, video, chapter_path, video_index)
            video_index += 1

    def download_video(self, course, video, chapter_path, video_index):
        """
        Download course video

        :param course:
        :param video:
        :param chapter_path:
        :param video_index:
        :return:
        """
        video_name = self.format_string(video["title"])
        video_slug = video["slug"]
        video_path = (
            chapter_path
            + "/"
            + "{} - {}.mp4".format(str(video_index).zfill(2), video_name)
        )
        if os.path.exists(video_path):
            self.print_log(
                "blue",
                "[*] ------ Skip video [{}] download "
                "because it already exists.".format(video_name),
            )
            return
        video_data = self.session.get(VIDEO_API_URL.format(course, video_slug))
        try:
            video_url = re.search(
                '"progressiveUrl":"(.+)","streamingUrl"', video_data.text
            ).group(1)
        except AttributeError:
            self.print_log(
                "red",
                "[!] ------ Can't download the video [{}], "
                "probably is only for premium users".format(video_name),
            )
            return
        self.print_log(
            "magenta", "[*] ------ Downloading video [{}]".format(video_name)
        )
        self.download_file(
            video_url,
            chapter_path,
            "{} - {}.mp4".format(str(video_index).zfill(2), video_name),
        )
        video_data = video_data.json()["elements"][0]
        if config.SUBS:
            try:
                subs = video_data["selectedVideo"]["transcript"]["lines"]
            except KeyError:
                self.print_log("gray", "[*] ------ No subtitles available")
            else:
                self.print_log("magenta", "[*] ------ Downloading subtitles")
                self.download_sub(
                    subs,
                    chapter_path,
                    "{} - {}.srt".format(str(video_index).zfill(2), video_name),
                )

    def download_exercise(self, exercises_list, course_name, course_path):
        if exercises_list:
            for exercise in exercises_list:
                try:
                    ex_name = exercise["name"]
                    ex_url = exercise["url"]
                except (KeyError, IndexError):
                    self.print_log(
                        "default",
                        "[!] --- Can't download an exercise file "
                        "for course [{}]".format(course_name),
                    )
                else:
                    exercise_path = "{}/{}".format(course_path, ex_name)
                    if os.path.exists(exercise_path):
                        self.print_log(
                            "blue",
                            "[*] ------ Skip exercise file [{}] download "
                            "because it already exists.".format(ex_name),
                        )
                        continue
                    self.print_log(
                        "magenta",
                        "[*] ------ Downloading exercise file [{}]".format(ex_name),
                    )
                    self.download_file(ex_url, course_path, ex_name)
        else:
            self.print_log("gray", "[*] --- No exercise files available")

    def search_courses(
        self, keywords="", sort="RECENCY", category="technology", limit=10
    ):
        """

        :param limit:
        :param category: technology|creative|business
        :param keywords:
        :param sort: RELEVANCE|RECENCY
        """
        token = self.session.cookies.get("JSESSIONID").replace('"', "")
        self.session.headers["Csrf-Token"] = token
        self.session.headers["Cookie"] = self.plain_cookies(
            requests.utils.dict_from_cookiejar(self.session.cookies)
        )
        self.session.headers.pop("Accept")
        resp = self.session.get(url=SEARCH_API_URL % (sort, category, keywords, limit))
        search_data = resp.json()["elements"]
        for course in search_data:
            title = course["hitInfo"]["com.linkedin.learning.api.search.SearchCourse"][
                "course"
            ]["title"]
            slug = course["hitInfo"]["com.linkedin.learning.api.search.SearchCourse"][
                "course"
            ]["slug"]
            print slug


def main():
    """

    """
    lld = Lld()
    lld.get_logged_session()
    # lld.search_courses()
    lld.download_courses()


if __name__ == "__main__":
    main()
