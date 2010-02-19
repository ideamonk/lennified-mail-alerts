# -*- coding: utf-8 -*-
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.api import urlfetch

import oauth
import feedparser
import urllib
import urllib2
from datetime import datetime
import tweetapp             # for twitter token structures TODO: merger / cleanup
from time import time
from random import getrandbits
import twitter_client
import webbrowser

# -------------------------------------------------------------------
# Google OAuth parameters
# -------------------------------------------------------------------
REQUEST_TOKEN_URL = 'https://www.google.com/accounts/OAuthGetRequestToken'
ACCESS_TOKEN_URL = 'https://www.google.com/accounts/OAuthGetAccessToken'
AUTHORIZATION_URL = 'https://www.google.com/accounts/OAuthAuthorizeToken'
CALLBACK_URL = 'http://lennified.appspot.com/oauth/token_ready'
RESOURCE_URL = 'https://mail.google.com/mail/feed/atom'
SCOPE = 'https://mail.google.com/mail/feed/atom'
CONSUMER_KEY = "lennified.appspot.com"
CONSUMER_SECRET = "rDkXTo1C5k4CFMA+DNPU45kg"



# -------------------------------------------------------------------
# Google OAuth DB Model
# -------------------------------------------------------------------
#
#
class OAuthToken(db.Model):
    user = db.UserProperty()
    token_key = db.StringProperty(required=True)
    token_secret = db.StringProperty(required=True)
    type = db.StringProperty(required=True)
    scope = db.StringProperty(required=True)
    lastcheck = db.StringProperty(required=False)


# -------------------------------------------------------------------
# Google OAuthPage
# -------------------------------------------------------------------
#   this class (probably should not be called a "page")
#   gets a request token and authorizes it
class OAuthPage(webapp.RequestHandler):
    def get(self):
        scope = {'scope':SCOPE}
        consumer = oauth.OAuthConsumer(CONSUMER_KEY, CONSUMER_SECRET)
        oauth_request = oauth.OAuthRequest.from_consumer_and_token(consumer, token=None,  http_url=REQUEST_TOKEN_URL,parameters=scope)
        signature_method = oauth.OAuthSignatureMethod_HMAC_SHA1()
        oauth_request.sign_request(signature_method, consumer, None)
        url = oauth_request.to_url()
        result = urlfetch.fetch(url)
        if result.status_code == 200:
            token = oauth.OAuthToken.from_string(result.content)
            #persist token
            saved_token = OAuthToken(user=users.GetCurrentUser(),
                                    token_key = token.key,
                                    token_secret = token.secret,
                                    scope = SCOPE,
                                    type = 'request',
                                    )
            saved_token.put()
            #now authorize token
            oauth_request = oauth.OAuthRequest.from_token_and_callback(token=token, callback=CALLBACK_URL, http_url=AUTHORIZATION_URL)
            url = oauth_request.to_url()
            self.redirect(url)
        else:
            self.response.out.write('no request token')


# -------------------------------------------------------------------
# Google OAuthReadyPage
# -------------------------------------------------------------------
#   this class is where we exchange the request token
#   for an access token
class OAuthReadyPage(webapp.RequestHandler):
    def get(self):
        t = OAuthToken.all()
        t.filter("user =",users.GetCurrentUser())
        t.filter("token_key =", self.request.get('oauth_token'))
        t.filter("scope =", SCOPE)
        t.filter("type =", 'request')
        results = t.fetch(1)
        for oauth_token in results:
            if oauth_token.token_key:
                key = oauth_token.token_key
                secret = oauth_token.token_secret
                token = oauth.OAuthToken(key,secret)
                #get access token
                consumer = oauth.OAuthConsumer(CONSUMER_KEY,CONSUMER_SECRET)
                oauth_request = oauth.OAuthRequest.from_consumer_and_token(consumer, token=token, http_url=ACCESS_TOKEN_URL)
                signature_method = oauth.OAuthSignatureMethod_HMAC_SHA1()
                oauth_request.sign_request(signature_method, consumer, token)
                url = oauth_request.to_url()
                result = urlfetch.fetch(url)
                if result.status_code == 200:
                    token = oauth.OAuthToken.from_string(result.content)
                    oauth_token.token_key = token.key
                    oauth_token.token_secret = token.secret
                    oauth_token.type = 'access'
                    oauth_token.put()
                    self.redirect('/')
                else:
                    self.response.out.write(result.content)
            else:
                    self.response.out.write('no go')


# -------------------------------------------------------------------
# MessageDispatcher
# -------------------------------------------------------------------
#   this class would handle work from the task queue
class Dispatcher(webapp.RequestHandler):
    def get(self):
        user = users.User(email = self.request.get('email'))
        atom = get_feed(user)
        if not atom:
            ''' Something went wrong here '''
            self.response.out.write ('something went wrong')
            # TODO: Log it
        else:
            # TEST self.response.out.write (atom)
            # okay got the atom now operate

            # get the user
            t = OAuthToken.all()
            t.filter("user =",user)
            t.filter("scope =", SCOPE)
            t.filter("type =", 'access')
            results = t.fetch(1)

            for lenny_user in results:
                current_tstamp = datetime.strptime (atom.feed.updated, "%Y-%m-%dT%H:%M:%SZ")
                try:
                    last_tstamp = datetime.strptime (lenny_user.lastcheck, "%Y-%m-%dT%H:%M:%SZ")
                except TypeError:
                    last_tstamp = datetime.strptime ("2000-2-3T12:34:34Z", "%Y-%m-%dT%H:%M:%SZ")

                if (last_tstamp < current_tstamp or 1==1):
                    # something new has come up, loop over and send em all

                    # Prepare a twitter oauthed client
                    service_info = tweetapp.OAUTH_APP_SETTINGS['twitter']
                    t = tweetapp.OAuthAccessToken.all()
                    t.filter ("user =", user)
                    tresults = t.fetch(1)
                    response_client = None
                    
                    for entry in tresults:
                        t_key = entry.oauth_token
                        t_secret = entry.oauth_token_secret
                        response_client = twitter_client.TwitterOAuthClient(service_info['consumer_key'], service_info['consumer_secret'], t_key, t_secret)
                        
                    for i in xrange(len(atom.entries)):
                        # mail_date = atom.entries[i].updated_parsed
                        mail_entry = atom.entries[i]
                        mail_tstamp = datetime.strptime ("%d-%d-%dT%d:%d:%dZ" % mail_entry.published_parsed[:6], "%Y-%m-%dT%H:%M:%SZ")
                        if (mail_tstamp > last_tstamp or 1==1):
                            # TEST:self.response.out.write(mail_entry.title)
                            # DM this message
                            if (response_client):
                                content = response_client.oauth_request('https://api.twitter.com/1/direct_messages/new.json', method='POST')
                                self.response.out.write ("%s #########" % content)
                                
                    lenny_user.lastcheck = atom.feed.updated
                    lenny_user.put()


# CORE MODULE FUNCTIONS
# =====================

# -------------------------------------------------------------------
# get_feed
# -------------------------------------------------------------------
#   fetches back a plaintext feed using feedparser
def get_feed(user):
    mail_feed = None
    if (user):
        t = OAuthToken.all()
        t.filter("user =",user)
        t.filter("scope =", SCOPE)
        t.filter("type =", 'access')
        results = t.fetch(1)

        for oauth_token in results:
            if oauth_token.token_key:
                key = oauth_token.token_key
                mail_feed = oauth_token.token_key
                secret = oauth_token.token_secret
                token = oauth.OAuthToken(key,secret)
                consumer = oauth.OAuthConsumer(CONSUMER_KEY,CONSUMER_SECRET)
                oauth_request = oauth.OAuthRequest.from_consumer_and_token(consumer,token=token,http_url=SCOPE)
                signature_method = oauth.OAuthSignatureMethod_HMAC_SHA1()
                oauth_request.sign_request(signature_method, consumer,token)
                result = urlfetch.fetch(url=SCOPE,  method=urlfetch.GET, headers=oauth_request.to_header(), deadline=10)
                mail_feed = feedparser.parse(result.content)

    return mail_feed
