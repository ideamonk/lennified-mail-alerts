# -*- coding: utf-8 -*-

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.api import urlfetch
from google.appengine.api.labs import taskqueue

import oauth
import feedparser
import urllib
import urllib2
from datetime import datetime
import tweetapp             # for twitter token structures TODO: merger / cleanup
from time import time, sleep
from random import getrandbits
import twitter_client
import webbrowser
from textwrap import wrap
from helpers import sanitize_codec
from django.utils import simplejson

# GLOBAL for DEBUG
DEBUG = True        # is false in production


# -------------------------------------------------------------------
# Google OAuth parameters
# -------------------------------------------------------------------
REQUEST_TOKEN_URL = 'https://www.google.com/accounts/OAuthGetRequestToken'
ACCESS_TOKEN_URL = 'https://www.google.com/accounts/OAuthGetAccessToken'
AUTHORIZATION_URL = 'https://www.google.com/accounts/OAuthAuthorizeToken'
CALLBACK_URL = 'http://lenny.madetokill.com/oauth/token_ready'
RESOURCE_URL = 'https://mail.google.com/mail/feed/atom'
SCOPE = 'https://mail.google.com/mail/feed/atom'
CONSUMER_KEY = "lenny.madetokill.com"
CONSUMER_SECRET = "KeY6MjEa/KkuvXTz7LTjFtTE"
TWITTER_MAX = 140


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
    email = db.StringProperty(required=False)
    step3 = db.StringProperty(required=False)

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

                    mail_feed = get_xml_from_token(token.key)
                    email_username=mail_feed.split("<title>Gmail - Inbox for ",1)[1].split("</title",1)[0]
                    oauth_token.email = email_username
                    oauth_token.put()
                    self.redirect('/home')
                else:
                    self.response.out.write(result.content)
            else:
                    self.response.out.write('no go')

    def post(self):
        self.get()

# -------------------------------------------------------------------
# DispatchQueue
# -------------------------------------------------------------------
#   adds all accounts for updates
class DispatchQueue(webapp.RequestHandler):
    def get(self):
        # get the user
        t = OAuthToken.all()
        t.filter("type =", 'access')
        user_list = t.fetch(1000)
        for a_user in user_list:
            t = tweetapp.OAuthAccessToken.all()
            t.filter("user =",a_user.user)
            results = t.fetch(1)
            try:
                if (results[0].enabled == 'true'):
                    # enqueue this user
                    if DEBUG==True:
                        if str(a_user.user.email()) == "ideamonk@gmail.com":
                            taskqueue.add(url="/dispatch?email=" +
                                        str(a_user.user.email()), method="GET")
                            self.response.out.write ("debug: done %s |" %
                                                        str(a_user.user.email()))
                    else:
                        taskqueue.add(url='/dispatch?email=' + str(a_user.user.email()), method='GET')
                        self.response.out.write("done %s |" % str(a_user.user.email()))
            except IndexError:
                ''' nothing was found on that user '''
                
    def post(self):
        self.get()
# -------------------------------------------------------------------
# MessageDispatcher
# -------------------------------------------------------------------
#   this class would handle work from the task queue
class Dispatcher(webapp.RequestHandler):
    def get(self):
        user = users.User(email = self.request.get('email'))
        atom = get_feed(user)

        if DEBUG==True:
            self.response.out.write(atom)

        if not atom:
            ''' Something went wrong here '''
            self.response.out.write ('something went wrong')
            # TODO: Log it
        else:
            if "Unauthorized" in atom.feed.subtitle:
                return

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

                if (last_tstamp < current_tstamp):
                    # something new has come up, loop over and send em all

                    # Prepare a twitter oauthed client
                    service_info = tweetapp.OAUTH_APP_SETTINGS['twitter']
                    t = tweetapp.OAuthAccessToken.all()
                    t.filter ("user =", user)
                    tresults = t.fetch(1)
                    
                    for entry in tresults:
                        t_key = entry.oauth_token
                        t_secret = entry.oauth_token_secret
                        response_client = twitter_client.TwitterOAuthClient(service_info['consumer_key'], service_info['consumer_secret'], t_key, t_secret)
                        twitter_user = entry.specifier
                        twitter_dm = entry.dm_store

                    for i in xrange(len(atom.entries)):
                        # mail_date = atom.entries[i].updated_parsed
                        mail_entry = atom.entries[i]
                        mail_tstamp = datetime.strptime ("%d-%d-%dT%d:%d:%dZ" % mail_entry.published_parsed[:6], "%Y-%m-%dT%H:%M:%SZ")
                        mail_strstamp = "%d-%d-%dT%d:%d:%dZ" % mail_entry.published_parsed[:6]
                        if (mail_tstamp > last_tstamp):
                            # TEST:self.response.out.write(mail_entry.title)
                            # DM this message
                            if (response_client):
                                # send a DM
                                mail_sender = wrap(mail_entry.author,20)[0]
                                if (len(mail_sender) == 20):
                                    mail_sender = mail_sender + ".."
                                try:
                                    mail_subject = wrap(mail_entry.title, 140-len(mail_sender)-8)[0]
                                except:
                                    mail_subject = mail_entry.title
                                    
                                if (len(mail_subject) == 140-len(mail_sender)-8):
                                    mail_subject = mail_subject + ".."
                                mail_notification = "L# " + mail_sender + " | " + mail_subject
                                twitter_params = {'user':twitter_user, 'text':mail_notification}
                                # get rid of ascii codec shite
                                twitter_params = sanitize_codec(twitter_params, 'utf-8')
                                content = response_client.oauth_request('https://api.twitter.com/1/direct_messages/new.json', twitter_params, method='POST')

                                # delete the last DM to avoid cluttering
                                if (twitter_dm == 'false'):
                                    try:
                                        old_dm_id = str(simplejson.loads(str(content))['id'])
                                        twitter_params = {'id':old_dm_id}
                                        content = response_client.oauth_request('https://api.twitter.com/1/direct_messages/destroy/' + old_dm_id + '.json', twitter_params, method='POST')
                                    except:
                                        ''' nothing to do '''

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

def get_xml_from_token(token):
    mail_feed = None
    if (token):
        t = OAuthToken.all()
        t.filter("token_key =",token)
        t.filter("scope =", SCOPE)
        t.filter("type =", 'access')
        results = t.fetch(1)

        for oauth_token in results:
            if oauth_token.token_key:
                key = oauth_token.token_key
                secret = oauth_token.token_secret
                token = oauth.OAuthToken(key,secret)
                consumer = oauth.OAuthConsumer(CONSUMER_KEY,CONSUMER_SECRET)
                oauth_request = oauth.OAuthRequest.from_consumer_and_token(consumer,token=token,http_url=SCOPE)
                signature_method = oauth.OAuthSignatureMethod_HMAC_SHA1()
                oauth_request.sign_request(signature_method, consumer,token)
                result = urlfetch.fetch(url=SCOPE,  method=urlfetch.GET, headers=oauth_request.to_header(), deadline=10)
                mail_feed = result.content

    return mail_feed
