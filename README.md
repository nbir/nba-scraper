# NBA Draft 2013 scraper

An incremental scraping service, which sits over `cbg-scrapy` scraping package, to collect tweets during the NBA Draft 2013. 

*Scraper* is an instance of `cbg-scrapy` modified according to the NBA streamer requirements

*Token Broker* brokers Twitter access token key-secret pairs.

*NBA Streamer* periodically checks if default keyword streams are working, and also creates follow-streams for users who tweet frequently about the topic.


## Scraper

```bash
$ python scrapy.py [-p <http API port>] [-l <path to log file>]
```

Settings file: `scrapy-settings.json`


### HTTP API


* ###Adding scrapers

	Adds (activates) new scrapers.

	URI: `/add/`
	
	GET parameters:
	
	```
	data:
	[{
	  "name": "LA Scraper",
	  "oauth": {
	    "token": "<Twitter's OAuth token>",
    	"secret": "<Twitter's OAuth secret>"
	  },
	  "filter": {
	    "id": "Some integer, unique for each scraper",
    	"location": [-122.75, 36.8, -121.75, 37.8],
	  }
	}]
	```
	
	Response:
	
	```js
	{
		"error": true | false,
		"message": "Error message"
	}
	```

* ### Listing scrapers
	
	Returnes state of active scrapers.
	
	URI: `/list/`
	
	GET parameters:
	
	```
	none
	```
	
	Response:
	
	```js
	[
		{
			"name": "LA scraper",
			"token": "<Twitter's OAuth token>",
			"status": "connecting" | "connected" | "failed",
			"ts_start": "2012.12.12T12:12:00",
			"received": 10000,
			"total_received": 100000,
			"limits": 5000,
			"total_limits": 60000,
			"rate": 10.4,			
			"last_received": "2012.12.12T12:12:00",
			"filter": {
				"track": ["#Python", "#Haskell"],
				"follow": [1, 2, 4],
				"locations" [0, 0, 0, 0]
			},
			"errors": [
				{
					"message": "error message",
					"ts": "2012.12.12T12:12:00"
				}
			]
		}
	]
	```
	
* ### Removing scrapers
	
	Stops and removes active scrapers.
	
	URI: `/remove/`
	
	GET parameters:
	
	```js
	data:
	[
		"<Twitter's OAuth token>"
	]
	```
	
	Response:
	
	```js
	{
		"error": true | false,
		"message": "Error message"
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

* ### Get data
	
	Returns list of hourly tweet counts so far.
	
	URI: `/data/`
	
	GET parameters:
	
	```
	none
	```
	
	Response:
	
	```
	[1, 2, 3, 4, 5]
	```
	
* ### Get collected
	
	Returns total tweets collected and total geo-tweets.
	
	URI: `/collected/`
	
	GET parameters:
	
	```
	none
	```
	
	Response:
	
	```
	{
		"total": 0,
		"geo": 0
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