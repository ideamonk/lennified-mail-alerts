# -*- coding: utf-8 -*-
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.api import urlfetch

import oauth, atomlib

# OAuth Access to gmail code borrowed from http://simplenotepad.appspot.com/text/goggle-app-engine-oauth-access-to-gmail

REQUEST_TOKEN_URL = 'https://www.google.com/accounts/OAuthGetRequestToken'
ACCESS_TOKEN_URL = 'https://www.google.com/accounts/OAuthGetAccessToken'
AUTHORIZATION_URL = 'https://www.google.com/accounts/OAuthAuthorizeToken'
CALLBACK_URL = 'http://lennified.appspot.com/oauth/token_ready'
RESOURCE_URL = 'https://mail.google.com/mail/feed/atom'
SCOPE = 'https://mail.google.com/mail/feed/atom'
CONSUMER_KEY = "lennified.appspot.com"
CONSUMER_SECRET = "rDkXTo1C5k4CFMA+DNPU45kg"

class OAuthToken(db.Model):
    user = db.UserProperty()
    token_key = db.StringProperty(required=True)
    token_secret = db.StringProperty(required=True)
    type = db.StringProperty(required=True)
    scope = db.StringProperty(required=True)

# the home page displays the nwest messages from the users inbox
# it looks for a saved access token, and if there is not one,redirects
# to /oauth to begin the dance...
class HomePage(webapp.RequestHandler):
    def get(self):
        mail_feed = ''
        t = OAuthToken.all()
        t.filter("user =",users.GetCurrentUser())
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
                result = urlfetch.fetch(url=SCOPE,  method=urlfetch.GET,
                                                                    headers=oauth_request.to_header())
                # I use a custom atom wrapper for displaying the feed
                mail_feed = atomlib.atom03.Atom.from_text(result.content)
        if not mail_feed:
                self.redirect('/oauth')
        self.response.out.write (mail_feed)

# this class (probably should not be called a "page")
# gets a request token and authorizes it
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

#this class is where we exchange the request token
# for an access token
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

application = webapp.WSGIApplication([
    ('/', HomePage),
    ('/oauth', OAuthPage),
    ('/oauth/token_ready', OAuthReadyPage),
], debug=True)

if __name__ == '__main__':
    run_wsgi_app(application)

