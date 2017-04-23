import monkey_patch  # noqa

from babel import negotiate_locale
from flask import Flask
from flask import abort
from flask import g
from flask import redirect
from flask import request
from flask import render_template
from flask import Response
from flask import url_for
from flask_babel import Babel
from werkzeug.contrib.fixers import ProxyFix
from werkzeug.contrib.profiler import ProfilerMiddleware

import config
import exceptions
import util

# Must import to run decorator
import template_context  # noqa
import line_format  # noqa

from forms import AjaxSearchForm
from forms import SearchForm
from grep import GrepBuilder

if config.DEBUG_PYINSTRUMENT:
    from pyinstrument import Profiler


app = Flask(__name__)
babel = Babel(app)


@app.route('/')
def index():
    networks = paths.networks()

    return render_template('index.html', networks=networks)


@app.route('/<network>/')
def network(network):
    try:
        channels = paths.channels(network)
    except exceptions.NoResultsException:
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
        _, canonical_channel = ex.args
        dates = paths.channel_dates(network, canonical_channel)
        g.canonical_url = url_for('channel', network=network, channel_=canonical_channel)
        return channel_(network, canonical_channel)


channel_ = channel


@app.route('/<network>/<channel>/<date>')
def log(network, channel, date):
    try:
        log = paths.log(network, channel, date)

        pagination_control = 1 + sum(bool(maybe) for maybe in (log.before, log.after))

        return render_template('log.html', network=network, channel=channel, date=date, pagination_control=pagination_control, log=log)
    except exceptions.NoResultsException as ex:
        abort(404)
    except exceptions.MultipleResultsException as ex:
        return render_template('error/multiple_results.html', network=network, channel=channel)
    except exceptions.CanonicalNameException as ex:
        info_type, canonical_data = ex.args

        if info_type == util.Scope.CHANNEL:
            channel = canonical_data
        elif info_type == util.Scope.DATE:
            date = canonical_data

        g.canonical_url = url_for('log', network=network, channel=channel, date=date)
        return log_(network, channel, date)


@app.route('/<network>/<channel>/<date>/raw')
def log_raw(network, channel, date):
    try:
        log = paths.log(network, channel, date)
        # Don't look, kids!
        _, (log_lines_only, _) = log.log.__reduce__()
        log_text = ''.join(list(log_lines_only))
        return Response(log_text, mimetype='text/plain')

    except exceptions.NoResultsException as ex:
        abort(404)
    except exceptions.MultipleResultsException as ex:
        return render_template('error/multiple_results.html', network=network, channel=channel)
    except exceptions.CanonicalNameException as ex:
        info_type, canonical_data = ex.args

        if info_type == util.Scope.CHANNEL:
            channel = canonical_data
        elif info_type == util.Scope.DATE:
            date = canonical_data

        return redirect(url_for('log_raw', network=network, channel=channel, date=date))


log_ = log


@app.route('/search/')
def search():
    # TODO: Expose multi-channel search
    form = SearchForm(request.args, csrf_enabled=False)
    valid = form.validate()

    network = form.network.data
    channel = form.channel.data

    if config.SEARCH_AJAX_ENABLED:
        if not valid:
            # TODO: Improve this?
            abort(404)

        try:
            dates = paths.channels_dates(network, [channel])
        except exceptions.NoResultsException:
            abort(404)
        except exceptions.MultipleResultsException:
            return render_template('error/multiple_results.html', network=network, channel=channel)

        max_segment = grep.max_segment(dates[-1]['date_obj'])

        return render_template('search_ajax.html', valid=valid, form=form, network=network, channel=channel, author=form.author.data, query=form.text.data, max_segment=max_segment)

    else:
        # We should have another copy of this to use...
        if not valid:
            results = []
        else:
            results = grep.run(
                channels=[channel],
                network=network,
                author=form.author.data,
                query=form.text.data,
            )

        return render_template('search.html', valid=valid, form=form, network=network, channel=channel, results=results)


@app.route('/search/chunk')
def search_ajax_chunk():
    form = AjaxSearchForm(request.args, csrf_enabled=False)
    valid = form.validate()

    date_start, date_end = grep.segment_bounds(form.segment.data)

    # We should have another copy of this to use...
    if not valid:
        results = []
    else:
        results = grep.run(
            channels=[form.channel.data],
            network=form.network.data,
            author=form.author.data,
            query=form.text.data,
            date_range=[date_start, date_end],
        )

    return render_template('search_result.html', network=form.network.data, channels=[form.channel.data], results=results)


@app.errorhandler(404)
def not_found(ex):
    return render_template('error/not_found.html'), 404


@babel.localeselector
def get_locale():
    from_cookie = request.cookies.get('lang', None)

    if from_cookie and from_cookie in config.LOCALE_PREFER:
        return from_cookie
    else:
        preferred = [x.replace('-', '_') for x in request.accept_languages.values()]
        return negotiate_locale(preferred, config.LOCALE_PREFER)


def inject_profiler():
    request.profiler = Profiler(use_signal=False)
    request.profiler.start()

def output_profiler(response):
    request.profiler.stop()
    print(request.profiler.output_text(unicode=True, color=True))
    return response

def create():
    global paths, grep

    paths = getattr(log_path, config.LOG_PATH_CLASS)()
    grep = GrepBuilder(paths)

    util.register_context_processors(app)
    util.register_template_filters(app)

    from auth import auth
    app.register_blueprint(auth, url_prefix='/auth')

    app.secret_key = config.SECRET_KEY
    # Produces actual debug under internal server. Produces stderr under uwsgi
    app.debug = True

    # Not app.jinja_options, because ???
    # app.jinja_env.bytecode_cache = FileSystemBytecodeCache()

    if config.FLASK_PROXY:
        app.wsgi_app = ProxyFix(app.wsgi_app)

    if config.DEBUG_PROFILER:
        app.config['PROFILE'] = True
        app.wsgi_app = ProfilerMiddleware(app.wsgi_app, restrictions=[30])

    if config.DEBUG_PYINSTRUMENT:
        app.before_request(inject_profiler)
        app.after_request(output_profiler)

    return app


if __name__ == '__main__':
    create()

    app.run(host='0.0.0.0', debug=True)
