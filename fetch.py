import argparse, os, sys, traceback
import hashlib
import random
import redis
import requests
from datetime import date
from pyquery import PyQuery as PQ
from twython import Twython

TWITTER_CONSUMER_KEY = os.environ['TWITTER_CONSUMER_KEY']
TWITTER_CONSUMER_SECRET = os.environ['TWITTER_CONSUMER_SECRET']
TWITTER_ACCESS_TOKEN = os.environ['TWITTER_ACCESS_TOKEN']
TWITTER_ACCESS_SECRET = os.environ['TWITTER_ACCESS_SECRET']

DATA_ROOT = 'http://gd2.mlb.com/components/game/mlb/'
REDIS_KEYS = {
    'start': 'start_count',
    'current': 'current_count',
    'target': 'target_count',
}
# ICHIRO MLB ID 400085
# 621043 borrowing Carlos Correa's 4/6/2016 for testing
CONFIG = {
    'playerID': '400085',
    'team': 'MIA',
    'player_name': 'Ichiro',
    'start_count': 2935,
    'target_count': 3000,
    'events_tracked': ['Single', 'Double', 'Triple', 'Home Run'],
}


def create_redis_connection():
    redis_url = os.getenv('REDISTOGO_URL', 'redis://localhost:6379')
    r = redis.from_url(redis_url)
    
    return r


def flush_redis():
    '''
    Empty the current redis db
    '''
    r = create_redis_connection()
    r.flushdb()
    
    print 'Redis keys set to: ' + str(r.keys())
    
    
def check_redis():
    '''
    Check keys in current redis db
    '''
    r = create_redis_connection()
    
    for key in r.keys():
        print '{0}: {1}'.format(key, r.get(key))


def clean_the_lines():
    flush_redis()
    check_redis()
    
    print 'The lines are cleaned.'


def init_counts(r):
    '''
    Make sure redis has values for start, current, and target counts,
    and return those counts for possible calculations. 
    '''
    start = r.get(REDIS_KEYS['start'])
    if not start:
        start = CONFIG['start_count']
        r.set(REDIS_KEYS['start'], start)
        print 'Start count initialized.'
        
    current = r.get(REDIS_KEYS['current'])
    if not current:
        current = CONFIG['start_count']
        r.set(REDIS_KEYS['current'], current)

    if 'target_count' in CONFIG:
        target = r.get(REDIS_KEYS['target'])
        if not target:
            target = CONFIG['target_count']
            r.set(REDIS_KEYS['target'], target)
            print 'Target count initialized.'
    else:
        target = 0
        
    return int(start), int(current), int(target)


def fetch_events():
    # some constants for this scrape
    playerID = CONFIG['playerID']
    team = CONFIG['team']
    today = date.today()
    
    r = create_redis_connection()
    # borrowing Correa 4/6/2016 for testing
    # delete this key to force a match each scrape
    # and test addition to `current_count`
    #today = date(2016, 4, 6)
    #r.delete('gid_2016_04_06_houmlb_nyamlb_1-621043-AB4')
    #r.delete('gid_2016_04_06_houmlb_nyamlb_1-621043-AB5')
        
    # scrape the MLB game list page
    game_day_url = DATA_ROOT + 'year_{0}/month_{1}/day_{2}/'.format(today.year, '{:02d}'.format(today.month), '{:02d}'.format(today.day))
    page = PQ(game_day_url)
    # find the links on page
    game_links = [PQ(link).attr('href') for link in page('li a')]
    # we only care about game data links for player's team
    game_links = [link.strip('/') for link in game_links if 'gid' in link and team.lower() in link]

    # iterate through team's games for the day
    for gameID in game_links:
        # get the player's batter data file for this game
        data_url = game_day_url + gameID
        data_url += "/batters/{0}.xml".format(playerID)
        page = PQ(data_url)
        # just the at-bat events please
        atbats = page('atbats ab')

        # iterate through player's at-bats
        for index, event in enumerate(atbats):
            atbat = index+1
            # see if we've seen this at-bat
            rkey = "{0}-{1}-AB{2}".format(gameID, playerID, atbat)
            stored = r.get(rkey)

            # store results of new at-bats so we only
            # match against events we haven't seen
            if not stored:
                result = PQ(event).attr("event")
                match = result.lower() in [event.lower() for event in CONFIG['events_tracked']]
                r.set(rkey, result)
                
                # if we match, do a thing
                if match:
                    handle_match(result)
                else:
                    handle_miss(result)
               
    print 'Done with scrape.' 


def handle_miss(result):
    player_name = CONFIG['player_name']
    WISHES = [
        "",
        "That's OK, we still love you Ichiro.",
        "Get 'em next time!",
        "We still believe! Go go go go, Ichiro https://t.co/9M0uBIG89B",
    ]
    message = "{0} {1} :( ".format(player_name, result.lower())
    message += random.choice(WISHES)

    tweet_message(message)
    

def handle_match(result):
    r = create_redis_connection()
    # get our counts
    start, current, target = init_counts(r)
    # update current total
    new_total = current+1
    r.set(REDIS_KEYS['current'], new_total)
    
    # make a nice message for this match
    player_name = CONFIG['player_name']
    message = "{0} {1}! ".format(player_name, result.lower())
    
    if target > 0:
        message += "Thats's {:,}, only {:,} to go till {:,}.".format(new_total, (target-new_total), target)
    else:
        message += "That's {:,} so far.".format(current)

    tweet_message(message)


def tweet_message(message):
    # auth with Twitter
    twitter = Twython(
        TWITTER_CONSUMER_KEY, TWITTER_CONSUMER_SECRET,
        TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET
    )
    # make sure our tweet is short enough
    tweet = check_tweet(message)
    # send it
    twitter.update_status(status=tweet)


def check_tweet(tweet):
    if len(tweet) > 140:
        tweet = tweet[:137] + '...'

    return tweet


def process_args(arglist=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_const', const=True)
    parser.add_argument('--flush', action='store_const', const=True)
    parser.add_argument('--clean', action='store_const', const=True)
    args = parser.parse_args()
    
    return args


def main(args=None):
    if args is None:
        args = sys.argv[1:]
    args = process_args(args)
        
    if args.flush:
        flush_redis()
    elif args.check:
        check_redis()
    elif args.clean:
        clean_the_lines()
    else:
        fetch_events()

if __name__ == '__main__':
    try:
        main()
    except Exception, e:
        sys.stderr.write('\n')
        traceback.print_exc(file=sys.stderr)
        sys.stderr.write('\n')
        sys.exit(1)

