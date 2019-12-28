import re
from requests_html import HTMLSession
from datetime import datetime
from urllib.parse import quote
from bs4 import BeautifulSoup
from logger import Logger

session = HTMLSession()

def get_tweets(query, pages=25):
    """Gets tweets for a given user, via the Twitter frontend API."""

    logger = Logger()
    after_part = 'include_available_features=1&include_entities=1&include_new_items_bar=true'
    if query.startswith('#'):
        query = quote(query)
        url = 'https://twitter.com/i/search/timeline?f=tweets&vertical=default&q={}&src=tyah&reset_error_state=false&'.format(query)
    else:
        url = 'https://twitter.com/i/profiles/show/{}/timeline/tweets?'.format(query)
    url += after_part
    
    headers = {
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Referer': 'https://twitter.com/{}'.format(query),
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/603.3.8 (KHTML, like Gecko) Version/10.1.2 Safari/603.3.8',
        'X-Twitter-Active-User': 'yes',
        'X-Requested-With': 'XMLHttpRequest',
        'Accept-Language': 'en-US'
    }

    def gen_tweets(pages):
        logger.add("MSG: Sending request to url '{}'...".format(url))
        r = session.get(url, headers=headers)

        logger.add("MSG: Parsing result...".format(url))
        while pages > 0:
            try:
                html = BeautifulSoup(r.json()['items_html'], parser='html', features="lxml")
            except KeyError:
                raise ValueError(
                    'Oops! Either "{}" does not exist or is private.'.format(query))

            comma = ","
            dot = "."
            tweets = []
            for tweet in html.select('.stream-item'):
                # 10~11 html elements have `.stream-item` class and also their `data-item-type` is `tweet`
                # but their content doesn't look like a tweet's content
                try:
                    text = tweet.select('.tweet-text')[0].get_text()
                except IndexError:  # issue #50
                    continue

                tweet_id = tweet['data-item-id']

                time = datetime.fromtimestamp(int(tweet.select('._timestamp')[0]['data-time-ms']) / 1000.0)

                interactions = [
                    x.get_text()
                    for x in tweet.select('.ProfileTweet-actionCount')
                ]

                replies = int(
                    interactions[0].split(' ')[0].replace(comma, '').replace(dot, '')
                    or interactions[3]
                )

                retweets = int(
                    interactions[1].split(' ')[0].replace(comma, '').replace(dot, '')
                    or interactions[4]
                    or interactions[5]
                )

                likes = int(
                    interactions[2].split(' ')[0].replace(comma, '').replace(dot, '')
                    or interactions[6]
                    or interactions[7]
                )

                hashtags = [
                    hashtag_node.get_text()
                    for hashtag_node in tweet.select('.twitter-hashtag')
                ]
                urls = [
                    url_node['data-expanded-url']
                    for url_node in tweet.select('a.twitter-timeline-link:not(.u-hidden)')
                ]
                photos = [
                    photo_node['data-image-url']
                    for photo_node in tweet.select('.AdaptiveMedia-photoContainer')
                ]

                is_retweet = False
                if tweet.select('.js-stream-tweet')[0].has_attr('data-retweet-id'):
                    is_retweet = True

                is_pinned = False
                if tweet.select(".pinned"):
                    is_pinned = True

                videos = []
                video_nodes = tweet.select(".PlayableMedia-player")
                for node in video_nodes:
                    styles = node['style'].split()
                    for style in styles:
                        if style.startswith('background'):
                            tmp = style.split('/')[-1]
                            video_id = tmp[:tmp.index('.jpg')]
                            videos.append({'id': video_id})

                tweets.append({
                    'tweetId': tweet_id,
                    'isRetweet': is_retweet,
                    'time': time,
                    'text': text,
                    'replies': replies,
                    'retweets': retweets,
                    'likes': likes,
                    'isPinned': is_pinned,
                    'entries': {
                        'hashtags': hashtags, 'urls': urls,
                        'photos': photos, 'videos': videos
                    }
                })


            last_tweet = html.select('.stream-item')[-1]['data-item-id']

            for tweet in tweets:
                if tweet:
                    tweet['text'] = re.sub(r'\Shttp', ' http', tweet['text'], 1)
                    tweet['text'] = re.sub(r'\Spic\.twitter', ' pic.twitter', tweet['text'], 1)
                    yield tweet

            r = session.get(url, params={'max_position': last_tweet}, headers=headers)
            pages += -1
    yield from gen_tweets(pages)

# for searching:
#
# https://twitter.com/i/search/timeline?vertical=default&q=foof&src=typd&composed_count=0&include_available_features=1&include_entities=1&include_new_items_bar=true&interval=30000&latent_count=0
# replace 'foof' with your query string.  Not sure how to decode yet but it seems to work.
