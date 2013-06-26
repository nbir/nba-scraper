#!/usr/bin/python
# -*- coding: utf-8 -*-

# Author: Nibir Bora <nbora@usc.edu>
# URL: <http://cbg.isi.edu/>
# For license information, see LICENSE


import os
import sys
import csv
import logging
import datetime
import argparse
import requests
import psycopg2
import traceback
import anyjson as json

from twisted.python import log
from hoopshype import HoopsHype
from twisted.internet import reactor
from twisted.web import server, resource
from twisted.internet.task import LoopingCall
from twisted.python.logfile import DailyLogFile

global LOG_FILE

VERSION = "1.0"


def read_settings(filepath="nba-settings.json"):
    json_file = open(filepath, "r")
    settings = json.loads(json_file.read())
    json_file.close()
    return settings

def iso_time(ts):
    return ts.strftime("%Y-%m-%dT%H:%M:%S")


class DefaultStreamer(object):

    class Status(object):

        CONNECTED = 1
        CONNECTING = 0
        FAILED = -1

    def __init__(self):
        settings = read_settings("nba-settings.json")
        scrapy_settings = read_settings("scrapy-settings.json")
        broker_settings = read_settings("broker-settings.json")
        self.default_file = settings["default"]["filename"]
        self.scrapy_url = "http://%s:%d" % (scrapy_settings["api"]["host"], 
                                            scrapy_settings["api"]["port"])
        self.broker_url = "http://%s:%d" % (broker_settings["api"]["host"], 
                                            broker_settings["api"]["port"])

    def stream(self):
        log.msg("Default streamer started.")
        running_fltr = self._get_running_filters()
        default_fltr = self._load_default_filters()
        for fid in default_fltr:
            if fid not in running_fltr:
                self._launch_stream(str(fid), default_fltr[fid])

    def _get_running_filters(self):
        filters = {}
        text_response = requests.get("%s/list/" % self.scrapy_url).text
        response = json.loads(text_response)
        for stream in response:
            filters[stream["filter"]["id"]] = stream["filter"]
        return filters

    def _load_default_filters(self):
        filters = {}
        with open(self.default_file, 'rb') as fp:
            cr = csv.reader(fp, delimiter=',')
            for fltr in cr:
                filters[fltr.pop(0)] = fltr
        return filters

    def _launch_stream(self, fid, track):
        while(True):
            text_response = requests.get("%s/get/" % self.broker_url).text
            token = json.loads(text_response)
            if "token" in token and "secret" in token:
                break;

        opt = {
            "name": "Default scraper " + str(fid),
            "oauth": token,
            "filter": {
                "id": fid,
                "track": track,
            }
        }
        scrapy_params = {"data": json.dumps([opt])}
        status = json.loads(requests.get("%s/add/" % self.scrapy_url, 
                                        params=scrapy_params).text)
        if "success" in status:
            log.msg("Added stream %s: %r, " % (fid, json.dumps(opt)))
        elif "error" in status:
            log.msg("Error adding stream %s: %r, " % (fid, json.dumps(opt)))
        else:
            log.msg("Unknown status of stream %s: %r, " % (fid, json.dumps(opt)))


class FollowStreamer(object):

    class Status(object):

        CONNECTED = 1
        CONNECTING = 0
        FAILED = -1

    def __init__(self):
        settings = read_settings("nba-settings.json")
        scrapy_settings = read_settings("scrapy-settings.json")
        broker_settings = read_settings("broker-settings.json")
        self.id_from = settings["follow"]["id_from"]
        self.limit = settings["follow"]["limit"]
        self.min_tweets = settings["follow"]["min_tweets"]
        self.db_string = "host='{host}' dbname='{dbname}' user='{user}' \
                        password='{password}'".format(
                            password = settings["database"]["password"],
                            user = settings["database"]["username"],
                            dbname = settings["database"]["name"],
                            host = settings["database"]["host"],
                            port = settings["database"]["port"],
                            )
        self.tweet_table = settings["database"]["tweet_table"]
        self.scrapy_url = "http://%s:%d" % (scrapy_settings["api"]["host"], 
                                            scrapy_settings["api"]["port"])
        self.broker_url = "http://%s:%d" % (broker_settings["api"]["host"], 
                                            broker_settings["api"]["port"])

    def stream(self):
        log.msg("Follow streamer started.")
        following, streams = self._get_following_list()
        user_ids = self._find_interesting_users()
        user_ids = [uid for uid in user_ids if uid not in following]

        if len(streams) > 0:
        # stop and rebuild ALL streams with follow > limit
            for fid, count in streams.items():
                if count > self.limit:
                    user_ids.extend(self._stop_stream(fid))
                    del streams[fid]

        if len(user_ids) > 0:
            if len(streams) > 0:
                # stop and rebuild ONlY ONE streams with follow < limit
                fid, count = streams.items().pop()
                user_ids.extend(self._stop_stream(fid))

            splits = []
            while(True):
                # prepare splits of size <= limit
                if len(user_ids) <= self.limit:
                    splits.append(user_ids[:self.limit])
                    break
                splits.append(user_ids[:self.limit])
                user_ids = user_ids[self.limit:]

            used_fids = self._get_used_fids()
            new_fids = range(self.id_from, 100)
            new_fids.reverse()
            for fid in used_fids:
                if fid >= self.id_from: new_fids.remove(fid)
            for follow in splits:
                fid = str(new_fids.pop())
                self._launch_stream(fid, follow)

    def _get_following_list(self):
        streams = {}
        following = []
        text_response = requests.get("%s/list/" % self.scrapy_url).text
        response = json.loads(text_response)
        for stream in response:
            if int(stream["filter"]["id"]) >= self.id_from \
            and "follow" in stream["filter"]:
                following.extend(stream["filter"]["follow"])
                l = len(stream["filter"]["follow"])
                if l != self.limit:
                    streams[stream["filter"]["id"]] = l

        return following, streams

    def _get_used_fids(self):
        while(True):
            text_response = requests.get("%s/list/" % self.scrapy_url).text
            response = json.loads(text_response)
            if type(response) is list:
                break;
        fids = [int(stream["filter"]["id"]) for stream in response]
        return fids

    def _find_interesting_users(self):
        SQL = '''SELECT user_id, COUNT(*) AS c
                FROM {rel_tweet}
                GROUP BY user_id
                ORDER BY c'''.format(rel_tweet=self.tweet_table)
        con = psycopg2.connect(self.db_string)
        cur = con.cursor()
        cur.execute(SQL)
        recs = cur.fetchall()
        user_ids = [str(rec[0]) for rec in recs if rec[1] > self.min_tweets]
        con.close()
        return user_ids

    def _stop_stream(self, fid):
        text_response = requests.get("%s/list/" % self.scrapy_url).text
        slist = json.loads(text_response)
        tokens = []
        user_ids = []
        for stream in slist:
            if stream["filter"]["id"] == fid:
                tokens.append(stream["token"])
                if "follow" in stream["filter"]:
                    user_ids.extend(stream["filter"]["follow"])

        scrapy_params = {"data": json.dumps(tokens)}
        status = json.loads(requests.get("%s/remove/" % self.scrapy_url, params=scrapy_params).text)
        log.msg("Stopped stream %s: %r, " % (fid, json.dumps(status)))

        return user_ids

    def _launch_stream(self, fid, follow):
        while(True):
            text_response = requests.get("%s/get/" % self.broker_url).text
            token = json.loads(text_response)
            if "token" in token and "secret" in token:
                break;

        opt = {
            "name": "Follow scraper " + str(fid),
            "oauth": token,
            "filter": {
                "id": fid,
                "follow": follow,
            }
        }
        scrapy_params = {"data": json.dumps([opt])}
        status = json.loads(requests.get("%s/add/" % self.scrapy_url, 
                                        params=scrapy_params).text)
        if "success" in status:
            log.msg("Added stream %s: %r, " % (fid, json.dumps(opt)))
        elif "error" in status:
            log.msg("Error adding stream %s: %r, " % (fid, json.dumps(opt)))
        else:
            log.msg("Unknown status of stream %s: %r, " % (fid, json.dumps(opt)))


class HoopshypeStreamer(object):

    class Status(object):

        CONNECTED = 1
        CONNECTING = 0
        FAILED = -1

    def __init__(self):
        settings = read_settings("nba-settings.json")
        scrapy_settings = read_settings("scrapy-settings.json")
        broker_settings = read_settings("broker-settings.json")
        self.id_from = settings["follow"]["id_from"]
        self.limit = settings["follow"]["limit"]
        self.min_tweets = settings["follow"]["min_tweets"]
        self.scrapy_url = "http://%s:%d" % (scrapy_settings["api"]["host"], 
                                            scrapy_settings["api"]["port"])
        self.broker_url = "http://%s:%d" % (broker_settings["api"]["host"], 
                                            broker_settings["api"]["port"])

    def stream(self):
        log.msg("Hoopshype streamer started.")
        following, streams = self._get_following_list()
        hoops = HoopsHype()
        user_ids = hoops.get()
        user_ids = [uid for uid in user_ids if uid not in following]
        hcount = int(open('hoopshype.txt','rb').read())
        hcount += len(user_ids)
        open('hoopshype.txt','wb').write(str(hcount))

        if len(streams) > 0:
        # stop and rebuild ALL streams with follow > limit
            for fid, count in streams.items():
                if count > self.limit:
                    user_ids.extend(self._stop_stream(fid))
                    del streams[fid]

        if len(user_ids) > 0:
            if len(streams) > 0:
                # stop and rebuild ONlY ONE streams with follow < limit
                fid, count = streams.items().pop()
                user_ids.extend(self._stop_stream(fid))

            splits = []
            while(True):
                # prepare splits of size <= limit
                if len(user_ids) <= self.limit:
                    splits.append(user_ids[:self.limit])
                    break
                splits.append(user_ids[:self.limit])
                user_ids = user_ids[self.limit:]

            used_fids = self._get_used_fids()
            new_fids = range(self.id_from, 100)
            new_fids.reverse()
            for fid in used_fids:
                if fid >= self.id_from: new_fids.remove(fid)
            for follow in splits:
                fid = str(new_fids.pop())
                self._launch_stream(fid, follow)

    def _get_following_list(self):
        streams = {}
        following = []
        while(True):
            text_response = requests.get("%s/list/" % self.scrapy_url).text
            response = json.loads(text_response)
            if type(response) is list:
                break;
        for stream in response:
            if int(stream["filter"]["id"]) >= self.id_from \
            and "follow" in stream["filter"]:
                following.extend(stream["filter"]["follow"])
                l = len(stream["filter"]["follow"])
                if l != self.limit:
                    streams[stream["filter"]["id"]] = l

        return following, streams

    def _get_used_fids(self):
        while(True):
            text_response = requests.get("%s/list/" % self.scrapy_url).text
            response = json.loads(text_response)
            if type(response) is list:
                break;
        fids = [int(stream["filter"]["id"]) for stream in response]
        return fids

    def _stop_stream(self, fid):
        text_response = requests.get("%s/list/" % self.scrapy_url).text
        slist = json.loads(text_response)
        tokens = []
        user_ids = []
        for stream in slist:
            if stream["filter"]["id"] == fid:
                tokens.append(stream["token"])
                if "follow" in stream["filter"]:
                    user_ids.extend(stream["filter"]["follow"])

        scrapy_params = {"data": json.dumps(tokens)}
        status = json.loads(requests.get("%s/remove/" % self.scrapy_url, params=scrapy_params).text)
        log.msg("Stopped stream %s: %r, " % (fid, json.dumps(status)))

        return user_ids

    def _launch_stream(self, fid, follow):
        while(True):
            text_response = requests.get("%s/get/" % self.broker_url).text
            token = json.loads(text_response)
            if "token" in token and "secret" in token:
                break;

        opt = {
            "name": "Follow scraper " + str(fid),
            "oauth": token,
            "filter": {
                "id": fid,
                "follow": follow,
            }
        }
        scrapy_params = {"data": json.dumps([opt])}
        status = json.loads(requests.get("%s/add/" % self.scrapy_url, 
                                        params=scrapy_params).text)
        if "success" in status:
            log.msg("Added stream %s: %r, " % (fid, json.dumps(opt)))
        elif "error" in status:
            log.msg("Error adding stream %s: %r, " % (fid, json.dumps(opt)))
        else:
            log.msg("Unknown status of stream %s: %r, " % (fid, json.dumps(opt)))


def get_data():
    try:
        settings = read_settings("nba-settings.json")
        db_string = "host='{host}' dbname='{dbname}' user='{user}' \
                    password='{password}'".format(
                        password = settings["database"]["password"],
                        user = settings["database"]["username"],
                        dbname = settings["database"]["name"],
                        host = settings["database"]["host"],
                        port = settings["database"]["port"])
        tweet_table = settings["database"]["tweet_table"]
        SQL = '''SELECT count(*)
            FROM {rel_tweet}
            GROUP BY timestamp::date, EXTRACT(hour FROM timestamp)
            ORDER BY timestamp::date, EXTRACT(hour FROM timestamp)
            '''.format(rel_tweet=tweet_table)
        con = psycopg2.connect(db_string)
        cur = con.cursor()
        cur.execute(SQL)
        recs = cur.fetchall()
        counts = [rec[0] for rec in recs]
        con.close()
        return counts
    except Exception:
        log.msg("Error, get_data: %s" % traceback.format_exc())
        return {"error" : True}

def get_collected():
    try:
        resp = {
            "total": 0,
            "geo": 0
            }
        settings = read_settings("nba-settings.json")
        db_string = "host='{host}' dbname='{dbname}' user='{user}' \
                    password='{password}'".format(
                        password = settings["database"]["password"],
                        user = settings["database"]["username"],
                        dbname = settings["database"]["name"],
                        host = settings["database"]["host"],
                        port = settings["database"]["port"])
        tweet_table = settings["database"]["tweet_table"]
        con = psycopg2.connect(db_string)
        cur = con.cursor()

        SQL = '''SELECT count(*)
            FROM {rel_tweet}'''.format(rel_tweet=tweet_table)
        cur.execute(SQL)
        recs = cur.fetchall()
        resp["total"] = recs[0][0]

        SQL = '''SELECT count(*)
            FROM {rel_tweet}
            WHERE geo <> 'NULL' '''.format(rel_tweet=tweet_table)
        cur.execute(SQL)
        recs = cur.fetchall()
        resp["geo"] = recs[0][0]
        con.close()
        return resp
    except Exception:
        log.msg("Error, get_collected: %s" % traceback.format_exc())
        return {"error" : True}


class NbaAPI(resource.Resource):
    isLeaf = True

    def __init__(self):
        resource.Resource.__init__(self)

    def render_GET(self, request):
        try:
            #log.msg("Handle request: %s" % request.path)
            request.setHeader("Content-Type", "application/json")
            request.setHeader("Access-Control-Allow-Origin", "*")

            if request.path == "/restart/":
                st1 = DefaultStreamer()
                st1.stream()
                st2 = FollowStreamer()
                st2.stream()
                return "done"
            elif request.path == "/data/":
                response = get_data()
                return json.dumps(response)
            elif request.path == "/collected/":
                response = get_collected()
                return json.dumps(response)

            elif request.path == "/hoops_users/":
                hcount = int(open('hoopshype.txt','rb').read())
                return str(hcount)
            elif request.path == "/restart_hoops/":
                st3 = HoopshypeStreamer()
                st3.stream()
                return "done"

            elif request.path == "/ping/":
                return "pong"
            elif request.path == "/log/":
                logfile = open("log-nba/daily-log.log")
                log_message = logfile.read()
                logfile.close()
                return log_message
            else:
                #log.msg("Wrong API path '%s'" % request.path, logLevel=logging.DEBUG)
                return json.dumps({
                    "error": True,
                    "message": "Wrong API path '%s'" % request.path,
                })

        except Exception:
            #log.msg("Error: %s" % traceback.format_exc())
            return json.dumps({
                "error": True,
                "message": traceback.format_exc(),
            })


def restart_default():
    try:
        st1 = DefaultStreamer()
        st1.stream()
    except Exception:
        log.msg("Error, restart default: %s" % traceback.format_exc())


def restart_follow():
    try:
        st2 = FollowStreamer()
        st2.stream()
    except Exception:
        log.msg("Error, restart follow: %s" % traceback.format_exc())

def restart_hoopshype():
    try:
        st3 = HoopshypeStreamer()
        st3.stream()
    except Exception:
        log.msg("Error, restart hoopshype: %s" % traceback.format_exc())    


MSG = \
"""
\n\n
.__   __. .______        ___       _______  .______          ___       _______ .___________. 
|  \ |  | |   _  \      /   \     |       \ |   _  \        /   \     |   ____||           | 
|   \|  | |  |_)  |    /  ^  \    |  .--.  ||  |_)  |      /  ^  \    |  |__   `---|  |----` 
|  . `  | |   _  <    /  /_\  \   |  |  |  ||      /      /  /_\  \   |   __|      |  |      
|  |\   | |  |_)  |  /  _____  \  |  '--'  ||  |\  \----./  _____  \  |  |         |  |      
|__| \__| |______/  /__/     \__\ |_______/ | _| `._____/__/     \__\ |__|         |__|      
     _______.___________..______       _______     ___      .___  ___.  _______ .______      
    /       |           ||   _  \     |   ____|   /   \     |   \/   | |   ____||   _  \     
   |   (----`---|  |----`|  |_)  |    |  |__     /  ^  \    |  \  /  | |  |__   |  |_)  |    
    \   \       |  |     |      /     |   __|   /  /_\  \   |  |\/|  | |   __|  |      /     
.----)   |      |  |     |  |\  \----.|  |____ /  _____  \  |  |  |  | |  |____ |  |\  \----.
|_______/       |__|     | _| `._____||_______/__/     \__\ |__|  |__| |_______|| _| `._____|
\n\n
Version: %s
Started on: %s UTC
PORT: %d
LOG: %r
PID: %d
SCRAPER: %s:%s/
BROKER: %s:%s/\n
"""

if __name__ == "__main__":
    settings = read_settings("nba-settings.json")
    scrapy_settings = read_settings("scrapy-settings.json")
    broker_settings = read_settings("broker-settings.json")

    port = settings["api"].get("port", 8002) if "api" in settings else 8002
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", default=port, type=int,
                        help="HTTP API port")
    parser.add_argument("-l", "--log", type=int, default=1,
                        help="Log-file")
    args = parser.parse_args()
    api_port = args.port
    log_file = "daily-log.log" if args.log else sys.stderr
    log_file = log_file
    if log_file is not sys.stderr:
        log_file = DailyLogFile(log_file, "%s/log-nba" % os.getcwd())
    MSG = MSG % (
        VERSION,
        datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
        api_port,
        log_file,
        os.getpid(),
        scrapy_settings["api"]["host"],
        scrapy_settings["api"]["port"],
        broker_settings["api"]["host"],
        broker_settings["api"]["port"],
    )
    sys.stdout.write(MSG)
    log.startLogging(log_file)

    api = NbaAPI()
    site = server.Site(api)
    reactor.listenTCP(api_port, site)

    lc1 = LoopingCall(lambda: restart_default())
    lc1.start(settings["default"]["interval"])

    lc2 = LoopingCall(lambda: restart_follow())
    lc2.start(settings["follow"]["interval"])

    lc3 = LoopingCall(lambda: restart_hoopshype())
    lc3.start(settings["hoopshype"]["interval"])
    
    reactor.run()

    log_file.close()