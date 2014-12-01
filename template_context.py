import subprocess
from urllib.parse import quote

from flask import request
from flask import session
from flask.ext.babel import gettext as _

import config
import util

@util.delay_context_processor
def get_encoded_path():
    """Get the URL-encoded path part of the input ``url``."""
    def inner(url):
        print(url)
        # '#' is an especially problematic character, since we want
        # the unquoted string to be '%23', not '#'
        path = url.split('/', 3)[-1].replace('#', '%23')
        return quote('/' + path)
    return dict(get_encoded_path=inner)

@util.delay_context_processor
def inject_encoded_url():
    path = request.path + '?' + request.query_string.decode('utf-8')
    return dict(encoded_path=path)

@util.delay_context_processor
def inject_session_user():
    return dict(session_user=session.get('user'))

@util.delay_context_processor
def inject_search_title_processor():
    def inner(search_term):
        if search_term:
            return _("search for %(search_term)s", search_term=search_term)
        return _("search")
    return dict(format_search_title=inner)

@util.delay_context_processor
def inject_title_processor():
    def inner(page_title):
        return "{} - {}".format(page_title, config.SITE_NAME)
    return dict(format_title=inner)

@util.delay_context_processor
def inject_site_brand():
    return dict(brand=config.SITE_NAME)

@util.delay_context_processor
def inject_git_status():
     p = subprocess.Popen(["git", "rev-parse", "HEAD"], stdout=subprocess.PIPE)
     revision, __ = p.communicate()

     dirty = False

     if p.returncode != 0:
         revision = None
     else:
         revision = revision.decode("utf-8").strip()[:8]
         p = subprocess.Popen(["git", "status", "--porcelain"], stdout=subprocess.PIPE)
         status, __ = p.communicate()
         if p.returncode == 0:
             if status.strip():
                 dirty = True

     return dict(git_status="{}{}".format(revision, _(" (dirty)") if dirty else ""))

