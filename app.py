from flask import Flask
from flask import abort
from flask import redirect
from flask import request
from flask import render_template
from flask import url_for

import config
import exceptions
import util

# Must import to run decorator
import template_context
import line_format

from forms import SearchForm
from grep import GrepBuilder
from log_path import LogPath

app = Flask(__name__)

# lol
paths = None

@app.route('/')
def index():
    networks = paths.networks()

    return render_template('index.html', networks=networks)

@app.route('/<network>/')
def network(network):
    try:
        channels = paths.channels(network)
    except exceptions.NoResultsException as ex:
        abort(404)

    return render_template('network.html', network=network, channels=channels)

@app.route('/<network>/<channel>/')
def channel(network, channel):
    try:
        dates = paths.channel_dates(network, channel)
        return render_template('channel.html', network=network, channel=channel, dates=dates)
    except exceptions.NoResultsException as ex:
        abort(404)
    except exceptions.MultipleResultsException as ex:
        return render_template('error/multiple_results.html', network=network, channel=channel)
    except exceptions.CanonicalNameException as ex:
        info_type, canonical_name = ex.args
        return redirect(url_for('channel', network=network, channel=canonical_name))

@app.route('/<network>/<channel>/<date>')
def log(network, channel, date):
    try:
        log = paths.log(network, channel, date)
        return render_template('log.html', network=network, channel=channel, date=date, log=log)
    except exceptions.NoResultsException as ex:
        abort(404)
    except exceptions.CanonicalNameException as ex:
        info_type, canonical_data = ex.args

        if info_type == util.Scope.CHANNEL:
            channel = canonical_data
        elif info_type == util.Scope.DATE:
            date = canonical_data

        return redirect(url_for('log', network=network, channel=channel, date=date))


@app.route('/search/')
def search():
    form = SearchForm(request.args, csrf_enabled=False)

    # A lot of this access control stuff will probably change once we allow
    # searches across multiple channels.

    valid = form.validate()

    # We should have another copy of this to use...
    if not paths.ac.evaluate('network', form.network.data) \
            or not paths.ac.evaluate('channel', form.channel.data):
        results = []

    else:

        grep = GrepBuilder() \
            .channels([form.channel.data]) \
            .dir(paths.network_to_path(form.network.data)) \
            .search(form.text.data)

        results = grep.run()

    return render_template('search.html', valid=valid, form=form, network=form.network.data, channel=form.channel.data, results=results)


@app.errorhandler(404)
def not_found(ex):
    return render_template('error/not_found.html'), 404

def create():
    global paths
    paths = LogPath()

    util.register_context_processors(app)
    util.register_template_filters(app)

    from auth import auth
    app.register_blueprint(auth, url_prefix='/auth')

    app.secret_key = config.SECRET_KEY
    app.debug = True

    return app

if __name__ == '__main__':
    create()

    app.run(host='0.0.0.0', debug=True)
