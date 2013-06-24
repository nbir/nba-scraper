-- Author: Nibir Bora <nbora@usc.edu>
-- URL: <http://cbg.isi.edu/>
-- For license information, see LICENSE


-- Tweet table
CREATE TABLE "nba_tweet" (
    "id" bigint NOT NULL PRIMARY KEY,
    "user_id" bigint NOT NULL,
    "timestamp" timestamp with time zone NOT NULL,
    "text" varchar(140) NOT NULL
);

SELECT AddGeometryColumn('public', 'nba_tweet', 'geo', 4326, 'POINT', 2);


-- Temporary tweet table
CREATE TABLE "nba_tmp_tweet" (
    "id" int8 NOT NULL,
    "user_id" int8 NOT NULL,
    "timestamp" timestamp(6) WITH TIME ZONE NOT NULL,
    "text" varchar(140) NOT NULL,
    "geo" "geometry",
    "status" int4 NOT NULL DEFAULT 0
)
WITH (OIDS=FALSE);

ALTER TABLE "nba_tmp_tweet" ADD CONSTRAINT "nba_tmp_tweets_pkey" PRIMARY KEY ("id");

CREATE INDEX "nba_tmp_tweet_status_idx" ON "nba_tmp_tweet" USING btree(status ASC NULLS LAST);
CREATE INDEX "nba_tmp_tweet_timestamp_idx" ON "nba_tmp_tweet" USING btree("timestamp" DESC NULLS FIRST);

CREATE RULE "tmp_tweet_ignore_dublicates" AS 
    ON INSERT TO "nba_tmp_tweet" 
    WHERE (EXISTS 
        (SELECT nba_tmp_tweet.id 
        FROM nba_tmp_tweet 
        WHERE (nba_tmp_tweet.id = new.id))) 
    DO INSTEAD NOTHING;


-- Limits table
CREATE TABLE "nba_tmp_limit" (
    "id" serial NOT NULL,
    "filter_id" int4,
    "timestamp" timestamp(6) WITH TIME ZONE NOT NULL,
    "value" int4 NOT NULL
)
WITH (OIDS=FALSE);

ALTER TABLE "nba_tmp_limit" ADD CONSTRAINT "nba_tmp_limit_pkey" PRIMARY KEY ("id");


-- Tweet JSON table
CREATE TABLE "nba_tmp_tweet_json" (
    "id" int8 NOT NULL,
    "filter_id" int4,
    "json" text NOT NULL
)
WITH (OIDS=FALSE);

ALTER TABLE "nba_tmp_tweet_json" ADD CONSTRAINT "nba_tmp_tweet_json_pkey" PRIMARY KEY ("id");

CREATE RULE "nba_tmp_tweet_json_ignore_duplicates" AS 
    ON INSERT TO "nba_tmp_tweet_json" 
    WHERE (EXISTS 
        (SELECT nba_tmp_tweet_json.id 
        FROM nba_tmp_tweet_json 
        WHERE (nba_tmp_tweet_json.id = new.id))) 
    DO INSTEAD NOTHING;

COMMIT;