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
import tweetapp

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
            # user has already logged in
           self.redirect ('/home')
        else:
            # The user has not logged in yet, show the landig page
            tValues = { 'page_title': 'Lenny.in - lennified notifications for gmail' }
            self.response.out.write(helpers.render ("homepage.html",tValues))


# Down Page
# -----------------------
# When lenny is under repair
#
class DownPage(webapp.RequestHandler):
    def get(self):
        user = users.GetCurrentUser()
        if (user):
            # user has already logged in
           self.redirect ('/home')
        else:
            # The user has not logged in yet, show the landig page
            tValues = { 'page_title': 'Lenny.in - lennified notifications for gmail' }
            self.response.out.write(helpers.render ("down.html",tValues))




# the home page displays the nwest messages from the users inbox
# it looks for a saved access token, and if there is not one,redirects
# to /oauth to begin the dance...
class HomePage(webapp.RequestHandler):
    def getGmailState(self):
        ''' gives back a boolean indicating if user has completed gmail step '''
        t = lenny.OAuthToken.all()
        t.filter("user =",users.GetCurrentUser())
        t.filter("scope =", lenny.SCOPE)
        t.filter("type =", 'access')
        results = t.fetch(1)
        if (len(results) == 1):
            return True
        else:
            return False

    def getTwitterState(self):
        ''' gives back a boolean indicating if user has completed twitter step '''
        t = lenny.tweetapp.OAuthAccessToken.all()
        t.filter ("user =", users.GetCurrentUser())
        results = t.fetch(1)
        if (len(results) == 1):
            return True
        else:
            return False

    def hasSeenSMS(self):
        t = lenny.OAuthToken.all()
        t.filter("user =",users.GetCurrentUser())
        t.filter("scope =", lenny.SCOPE)
        t.filter("type =", 'access')
        results = t.fetch(1)
        for r in results:
            if (r.step3 == "done"):
                return True
        return False
        
    def getUserState(self):
        ''' Gives back an integer indicating user's registration completeness '''
        if ( not self.getGmailState() ):
            return 1
        if ( not self.getTwitterState() ):
            return 2

        return 3

    def setSMSdone(self):
        t = lenny.OAuthToken.all()
        t.filter("user =",users.GetCurrentUser())
        t.filter("scope =", lenny.SCOPE)
        t.filter("type =", 'access')
        results = t.fetch(1)
        for r in results:
            r.step3="done"
            r.put()
            
    def showControlPanel(self):
        view={}
        view['logout_url'] = users.create_logout_url("/")
        view['user_email'] = users.GetCurrentUser()
        
        view['page_title'] = 'Control Panel - Lenny.in'
        page = "control.html"

        t = lenny.OAuthToken.all()
        t.filter("user =",users.GetCurrentUser())
        t.filter("scope =", lenny.SCOPE)
        t.filter("type =", 'access')
        results = t.fetch(1)
        for r in results:
            view['monitor_email'] =r.email

        t = tweetapp.OAuthAccessToken.all()
        t.filter("user =",users.GetCurrentUser())
        results = t.fetch(1)
        for r in results:
            view['monitor_twitter'] =r.specifier
            if (r.enabled=='true'):
                view['enable_url']='/home/control/disable'
                view['enable_or_disable']='disable'
            else:
                view['enable_url']='/home/control/enable'
                view['enable_or_disable']='enable'
                view['disable_style'] = "background:#888;"
                
            if (r.dm_store == None or r.dm_store == 'false'):
                view['dm_url']='/home/control/dm_store'
                view['save_or_dont']="preserve"
            else:
                view['dm_url']='/home/control/dm_destroy'
                view['save_or_dont']="don't store"
                
        self.response.out.write(helpers.render (page,view))

    def enableAlert(self):
        t = tweetapp.OAuthAccessToken.all()
        t.filter("user =",users.GetCurrentUser())
        results = t.fetch(1)
        for r in results:
            r.enabled = 'true'
            r.put()
        self.redirect('/home/control')

    def disableAlert(self):
        t = tweetapp.OAuthAccessToken.all()
        t.filter("user =",users.GetCurrentUser())
        results = t.fetch(1)
        for r in results:
            r.enabled = 'false'
            r.put()
        self.redirect('/home/control')

    def enableDMStore(self):
        t = tweetapp.OAuthAccessToken.all()
        t.filter("user =",users.GetCurrentUser())
        results = t.fetch(1)
        for r in results:
            r.dm_store = 'true'
            r.put()
        self.redirect('/home/control')
        
    def disableDMStore(self):
        t = tweetapp.OAuthAccessToken.all()
        t.filter("user =",users.GetCurrentUser())
        results = t.fetch(1)
        for r in results:
            r.dm_store = 'false'
            r.put()
        self.redirect('/home/control')
        
    def get(self, command=None):
        user = users.GetCurrentUser()
        if (user):
            if (command=='/done'):
                self.setSMSdone()
                self.redirect('/home/control')
                return

            #TODO: only if SMS
            if ('/control' in command and self.hasSeenSMS()):
                if ('/dm_store' in command):
                    self.enableDMStore()
                    return
                if ('/dm_destroy' in command):
                    self.disableDMStore()
                    return
                if ('/enable' in command):
                    self.enableAlert()
                    return
                if ('/disable' in command):
                    self.disableAlert()
                    return
                    
                self.showControlPanel()
                return
            
            # The user is already logged in, decide her fate depending on the extent to which
            # registration has been completed. -> step1, step2, control panel
            view={}
            view['user_email'] = users.GetCurrentUser()
            view['logout_url'] = users.create_logout_url("/")
            page="control.html"
            
            state = self.getUserState()
            
            if (state == 1):
                ''' user has not OAuthed Gmail, as her to '''
                view['page_title'] = 'Step 1 - Gmail Authentication - Lenny.in'
                page = "step1.html"

            if (state == 2):
                ''' user has not OAuthed Gmail, as her to '''
                view['page_title'] = 'Step 2 - Twitter Authentication - Lenny.in'
                page = "step2.html"

            if (state == 3):
                ''' user has not OAuthed Gmail, as her to '''
                view['page_title'] = 'Step 2 - Twitter Authentication - Lenny.in'
                page = "step3.html"

            if (self.hasSeenSMS()):
                self.redirect ("/home/control")
                
            self.response.out.write(helpers.render (page,view))
        else:
            self.redirect (users.create_login_url("/home"))


application = webapp.WSGIApplication([
    ('/old', WelcomePage),
    ('/', DownPage),
    ('/home(.*)', HomePage),
    ('/oauth', lenny.OAuthPage),
    ('/oauth/token_ready', lenny.OAuthReadyPage),
    ('/dispatch', lenny.Dispatcher),
    ('/dispatchall', lenny.DispatchQueue),
    ('/oauth/(.*)/(.*)', tweetapp.OAuthHandler),
], debug=True)

if __name__ == '__main__':
    run_wsgi_app(application)

