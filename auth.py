from urllib.parse import unquote, urlparse
from flask import Blueprint
from flask import flash
from flask import redirect
from flask import request
from flask import session
from flask import url_for
from flask_oauthlib.client import OAuth

import config

auth = Blueprint('auth', __name__, template_folder='templates')
oauth = OAuth()
google = oauth.remote_app(
    'google',
    app_key='GOOGLE',
    request_token_params={
        'scope': 'https://www.googleapis.com/auth/userinfo.email'
    },
    base_url='https://www.googleapis.com/oauth2/v1/',
    request_token_url=None,
    access_token_method='POST',
    access_token_url='https://accounts.google.com/o/oauth2/token',
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    consumer_key=config.GOOGLE_OAUTH_CONSUMER_KEY,
    consumer_secret=config.GOOGLE_OAUTH_CONSUMER_SECRET,
)

@google.tokengetter
def get_google_oauth_token():
    return session.get('google_token')


@auth.route('/')
@auth.route('/login')
def login():
    next_path = request.args.get('next')
    if next_path:
        # Since passing along the "next" URL as a GET param requires
        # a different callback for each page, and Google requires us to
        # whitelist each allowed callback page, we can't pass it as a GET
        # param. Instead, we sanitize and put into the session.
        request_components = urlparse(request.url)
        path = unquote(next_path)
        if path[0] == '/':
            # This first slash is unnecessary since we force it in when we
            # format next_url.
            path = path[1:]

        next_url = "{scheme}://{netloc}/{path}".format(
            scheme=request_components.scheme,
            netloc=request_components.netloc,
            path=path,
        )
        session['next_url'] = next_url
    return google.authorize(
        callback=url_for('.authorized', _external=True))


@auth.route('/logout')
def logout():
    session.pop('google_token', None)
    session.pop('user', None)
    return redirect(url_for('index'))


@auth.route('/login/authorized')
def authorized():
    resp = google.authorized_response()
    next_url = session.pop('next_url', url_for('index'))

    if resp is None:
        flash("You didn't sign in.")
        return redirect(next_url)

    session['google_token'] = (resp['access_token'], '')
    session['user'] = google.get('userinfo').data
    return redirect(next_url)
