#!/usr/bin/python
# -*- coding: utf-8 -*-

# Author: Nibir Bora <nbora@usc.edu>
# URL: <http://cbg.isi.edu/>
# For license information, see LICENSE


import os
import sys
import time
import urllib
import requests
import lxml.html
import oauth2 as oauth
import anyjson as json

from random import shuffle
from urllib import urlopen
from twisted.web import http
from twitter import Twitter, OAuth
from twisted.internet.defer import Deferred
from twisted.python.util import InsensitiveDict
from twisted.internet import protocol, ssl, reactor


def read_settings(filepath="nba-settings.json"):
    json_file = open(filepath, "r")
    settings = json.loads(json_file.read())
    json_file.close()
    return settings


class HoopsHype():

    def __init__(self):
        settings = read_settings("nba-settings.json")
        self.hoops_url = settings["hoopshype"]["host"]
        self.hoops_param = settings["hoopshype"]["param"]
        self.hoops_pages = settings["hoopshype"]["num_pages"]
        self.page_miss = 10
        scrapy_settings = read_settings("scrapy-settings.json")
        self.consumer_key = scrapy_settings["oauth"]["token"]
        self.consumer_secret = scrapy_settings["oauth"]["secret"]
        self.max_tries = 10
        broker_settings = read_settings("broker-settings.json")
        self.broker_url = "http://%s:%d" % (broker_settings["api"]["host"], 
                                            broker_settings["api"]["port"])

    def get(self):
        names = self._get_hoops_users()
        ids = self._map_name_to_id(names)
        return ids

    def _get_hoops_users(self):
        screen_names = []
        page_id = 1;
        while(True):
            try:
                url = self.hoops_url + '?' + self.hoops_param + '=' + str(page_id)
                doc = urlopen(url).read()
                tree = lxml.html.fromstring(doc)
                elements = tree.find_class('twtimeline_author_username')
                for el in elements:
                    try:
                        screen_names.append(el.text_content().replace('@', ''))
                    except:
                        pass
            except:
                self.page_miss -= 1

            page_id += 1
            if self.page_miss <= 0 or page_id > self.hoops_pages:
                break

        return list(set(screen_names))

    def _map_name_to_id(self, names):
        ids = []
        while(True):
            text_response = requests.get("%s/all/" % self.broker_url).text
            tokens = json.loads(text_response)
            if len(tokens) > 0 and "error" not in tokens:
                break;
        keys = tokens.keys()

        while(True):
            shuffle(keys)
            auth = OAuth(
                keys[0], tokens[keys[0]],
                self.consumer_key, self.consumer_secret)
            try:
                twitter = Twitter(auth=auth)
                profiles = twitter.users.lookup(screen_name=','.join(names[:100]))
                for prof in profiles:
                    try:
                        ids.append(str(prof['id_str']))
                    except:
                        pass

                names = names[100:]
                if len(names) <= 0:
                    break
            except:
                self.max_tries -= 1
                if self.max_tries <= 0:
                    break

        return ids


if __name__ == "__main__":
    hoops = HoopsHype()
    print json.dumps(hoops.get())

