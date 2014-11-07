# Makefile for uwsgi, because uwsgi sux

# App-specific config

include Makefile.appconfig

APP_MODULE = "app:create()"
PIDFILE = app.pid
VENV_NAME = python
UWSGI_LOG = uwsgi.log

# None of your business

BASEDIR = $(shell readlink -f .)
PIDPATH = $(BASEDIR)/$(PIDFILE)
VENV = $(BASEDIR)/$(VENV_NAME)
BIN = $(VENV)/bin/uwsgi

start:
	$(BIN) \
		--daemonize $(UWSGI_LOG) \
		--pidfile $(PIDFILE) \
		--http-socket $(BIND) \
		-H $(VENV) \
		-w $(APP_MODULE)

stop:
	$(BIN) --stop $(PIDFILE)

clean:
	rm static/style.css

css: static/style.css

static/style.css: static/style.css.scss
	$(VENV)/bin/pyscss < static/style.css.scss > static/style.css

init-env:
	ln -s ../bower_components static/vendor
