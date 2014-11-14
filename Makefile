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

.PHONY: tests

start: css ensure-stopped
	$(BIN) \
		--daemonize $(UWSGI_LOG) \
		--pidfile $(PIDFILE) \
		--http-socket $(BIND) \
		-H $(VENV) \
		-w $(APP_MODULE)

stop:
	$(BIN) --stop $(PIDFILE)
	while [ ! -z "`pgrep -F $(PIDFILE)`" ]; do sleep .1; done

ensure-stopped:
	@if [ -z "`pgrep -F $(PIDFILE)`" ]; then \
		exit 0; \
	else \
		echo "Cowardly refusing to run when another instance is already running."; \
		exit 1; \
	fi

restart: stop start

clean:
	rm static/style.css

css: static/style.css

static/style.css: static/style.css.scss
	$(VENV)/bin/pyscss < static/style.css.scss > static/style.css

init-env:
	ln -s ../bower_components static/vendor

tests:
	PYTHONPATH=. $(VENV)/bin/py.test -vvv tests
