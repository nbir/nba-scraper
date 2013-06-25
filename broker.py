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
import traceback
import anyjson as json

from twisted.python import log
from twisted.internet import reactor
from twisted.web import server, resource
from twisted.python.logfile import DailyLogFile

global LOG_FILE

VERSION = "1.0"


def read_settings(filepath="broker-settings.json"):
    json_file = open(filepath, "r")
    settings = json.loads(json_file.read())
    json_file.close()
    return settings


class BrokerAPI(resource.Resource):
    isLeaf = True

    def __init__(self):
        resource.Resource.__init__(self)
        settings = read_settings("broker-settings.json")
        scrapy_settings = read_settings("scrapy-settings.json")
        self.accounts_file = settings["csv"]["filename"]
        self.scrapy_url = "http://%s:%d" % (scrapy_settings["api"]["host"], scrapy_settings["api"]["port"])

    def _get_all_tokens(self):
        with open(self.accounts_file, 'rb') as fp:
            accounts = csv.reader(fp, delimiter=',')
            tokens = dict((acc[2], acc[3]) for acc in accounts)
        return tokens
            
    def _get_used_tokens(self):
        tokens = []
        while(True):
            text_response = requests.get("%s/list/" % self.scrapy_url).text
            response = json.loads(text_response)
            if len(response) == 0 or "token" in response[0]:
                break;
        for stream in response:
            tokens.append(str(stream["token"]))
        return tokens

    def get_nused_token(self):
        alltok = self._get_all_tokens()
        usedtok = self._get_used_tokens()
        for key in usedtok:
            if key in alltok: del alltok[key]
        if len(alltok) > 0:
            tok = alltok.items().pop()
            token = {
                "token" : tok[0],
                "secret" : tok[1]
                }
            return token
        else:
            return {"error" : "none"}

    def get_available(self):
        alltok = self._get_all_tokens()
        usedtok = self._get_used_tokens()
        available = {
            "total": len(alltok),
            "available": len(alltok),
            "used" : 0,
            }
        for key in usedtok:
            if key in alltok: available["used"] += 1
        available["available"] -= available["used"]
        return available

    def render_GET(self, request):
        try:
            #log.msg("Handle request: %s" % request.path, logLevel=logging.DEBUG)
            request.setHeader("Content-Type", "application/json")
            request.setHeader("Access-Control-Allow-Origin", "*")

            if request.path == "/get/":
                response = self.get_nused_token()
                return json.dumps(response)

            elif request.path == "/available/":
                response = self.get_available()
                return json.dumps(response)

            elif request.path == "/all/":
                response = self._get_all_tokens()
                return json.dumps(response)
            elif request.path == "/used/":
                response = self._get_used_tokens()
                return json.dumps(response)

            elif request.path == "/ping/":
                return "pong"
            elif request.path == "/log/":
                logfile = open("log-broker/daily-log.log")
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
            #log.msg("Error: %s" % traceback.format_exc(), logLevel=logging.WARNING)
            return json.dumps({
                "error": True,
                "message": traceback.format_exc(),
            })


MSG = \
"""
\n\n
.___________.  ______    __  ___  _______ .__   __. 
|           | /  __  \  |  |/  / |   ____||  \ |  | 
`---|  |----`|  |  |  | |  '  /  |  |__   |   \|  | 
    |  |     |  |  |  | |    <   |   __|  |  . `  | 
    |  |     |  `--'  | |  .  \  |  |____ |  |\   | 
    |__|      \______/  |__|\__\ |_______||__| \__| 
.______   .______        ______    __  ___  _______ .______      
|   _  \  |   _  \      /  __  \  |  |/  / |   ____||   _  \     
|  |_)  | |  |_)  |    |  |  |  | |  '  /  |  |__   |  |_)  |    
|   _  <  |      /     |  |  |  | |    <   |   __|  |      /     
|  |_)  | |  |\  \----.|  `--'  | |  .  \  |  |____ |  |\  \----.
|______/  | _| `._____| \______/  |__|\__\ |_______|| _| `._____|
\n\n
Version: %s
Started on: %s UTC
PORT: %d
LOG: %r
PID: %d
SCRAPER: %s:%s/\n
"""

if __name__ == "__main__":
    settings = read_settings()
    scrapy_settings = read_settings("scrapy-settings.json")
    port = settings["api"].get("port", 8001) if "api" in settings else 8001
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
        log_file = DailyLogFile(log_file, "%s/log-broker" % os.getcwd())
    MSG = MSG % (
        VERSION,
        datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
        api_port,
        log_file,
        os.getpid(),
        scrapy_settings["api"]["host"],
        scrapy_settings["api"]["port"],
    )
    sys.stdout.write(MSG)
    log.startLogging(log_file)

    api = BrokerAPI()
    site = server.Site(api)
    reactor.listenTCP(api_port, site)
    reactor.run()

    log_file.close()