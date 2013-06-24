# NBA Draft 2013 scraper

An incremental scraping service, which sits over `cbg-scrapy` scraping package, to collect tweets during the NBA Draft 2013. 

*Token Broker* brokers Twitter access token key-secret pairs.

*NBA Streamer* periodically checks if default keyword streams are working, and also creates follow-streams for users who tweet frequently about the topic.


## Token Broker
Run directives:

```bash
$ python broker.py [-p <http API port>] [-l <path to log file>]
```

Settings file: `broker-settings.json`

Requires: `scrapy-settings.json`

### HTTP API

* ### Get an unused token
	
	Returnes an unused access token key-secret pair.
	
	URI: `/get/`
	
	GET parameters:
	
	```
	none
	```
	
	Response:
	
	```
	{
		"token": "<Twitter's OAuth token>",
		"secret": "<Twitter's OAuth secret>"
	}
	```

* ### Get available
	
	Returnes number of used and available access tokens.
	
	URI: `/available/`
	
	GET parameters:
	
	```
	none
	```
	
	Response:
	
	```
	{
		"available": 5,
  		"used": 1
	}
	```
	
* ### Ping

	Returns string `pong`.
	
	URI: `/ping/`
	
	GET parameters:
	
	```
	none
	```
	Response:
	
	```
	pong
	```

* ### Log
	
	Returns log string.
	
	URI: `/log/`
	
	GET parameters:
	
	```
	none
	```


## NBA Streamer

Run directives:

```bash
$ python nba_streamer.py [-p <http API port>] [-l <path to log file>]
```

Settings file: `nba-settings.json`

Requires: `scrapy-settings.json`

### HTTP API



* ### Restart streams
	
	Force restart bothe default and follow streams.
	
	URI: `/restart/`
	
	GET parameters:
	
	```
	none
	```
	
	Response:
	
	```
	done
	```
	
* ### Ping

	Returns string `pong`.
	
	URI: `/ping/`
	
	GET parameters:
	
	```
	none
	```
	Response:
	
	```
	pong
	```

* ### Log
	
	Returns log string.
	
	URI: `/log/`
	
	GET parameters:
	
	```
	none
	```