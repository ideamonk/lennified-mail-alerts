# -*- coding: utf-8 -*-
import os
from google.appengine.ext.webapp import template

# Gives out template path 
def getPath(filename):
    path = os.path.join( os.path.dirname (__file__), "templates" )
    path = os.path.join (path,filename)
    return path

# returns a rendered template
def render(filename, values):
    return template.render(getPath(filename), values)

# gets rid of ascii codec shite
def sanitize_codec(fooDict,charset):
    return dict([(k, v.encode(charset)) for k, v in fooDict.items()])