# -*- coding: utf-8 -*-
# Lennified twitter notifications
# (C) 2010- Abhishek Mishra (ideamonk at gmail.com)

# AppEngine imports
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.api import urlfetch
from google.appengine.ext.webapp import template

# Local/ Pythonic imports
import os
import helpers
import LennyCore as lenny

# GLOBAL VARS
# -----------
#


# Default Landing page
# -----------------------
# welcomes the user, introduces the app
# 
class WelcomePage(webapp.RequestHandler):
    def get(self):
        user = users.GetCurrentUser()
        if (user):
            self.redirect ('/home')
        else:
            tValues = { 'fooVal': 'foo value' }
            self.response.out.write(helpers.render ("index.html", tValues))

# the home page displays the nwest messages from the users inbox
# it looks for a saved access token, and if there is not one,redirects
# to /oauth to begin the dance...
class HomePage(webapp.RequestHandler):
    def get(self):
        user = users.GetCurrentUser()
        if (user):
            self.response.out.write (' Control panel ')
        else:
            self.redirect (users.create_login_url("/home"))


application = webapp.WSGIApplication([
    ('/', WelcomePage),
    ('/home', HomePage),
    ('/oauth', lenny.OAuthPage),
    ('/oauth/token_ready', lenny.OAuthReadyPage),
    ('/dispatch', lenny.Dispatcher)
], debug=True)

if __name__ == '__main__':
    run_wsgi_app(application)

