# Makefile for uwsgi, because uwsgi sux

# App-specific config

include Makefile.appconfig

APP_MODULE = "app:create()"
PIDFILE = app.pid
VENV3_NAME = python3
VENV2_NAME = python2
UWSGI_LOG = uwsgi.log

# None of your business

BASEDIR = $(shell readlink -f .)
PIDPATH = $(BASEDIR)/$(PIDFILE)
VENV3 = $(BASEDIR)/$(VENV3_NAME)
BIN = $(VENV3)/bin/uwsgi

RM = rm -f

ifeq ($(shell which py.test),)
	PYTEST = $(VENV3)/bin/py.test
else
	PYTEST = $(shell which py.test)
endif

.PHONY: clean tests translations-rescan translations-update translations-compile

start: css ensure-stopped
	$(BIN) \
		--daemonize $(UWSGI_LOG) \
		--pidfile $(PIDFILE) \
		--http-socket $(BIND) \
		-H $(VENV3) \
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
	$(RM) static/style.css
	$(RM) messages.pot
	$(RM) *.stamp

last-exception:
	@sed -nE '/^Traceback/,/^\[pid: /p' $(UWSGI_LOG) | tac | sed '/^Traceback/q' | tac

css: static/style.css

static/style.css: static/style.css.scss static/vendor/bootstrap-sass-official/assets/stylesheets/_bootstrap.scss
	$(VENV3)/bin/pyscss < static/style.css.scss > static/style.css

init-env:
	ln -s ../bower_components static/vendor

init-pythons:
	virtualenv --python=python3 --no-site-packages $(VENV3_NAME)
	$(VENV3)/bin/pip install -r requirements-3.txt
	virtualenv --python=python2 --no-site-packages $(VENV2_NAME)
	$(BASEDIR)/$(VENV2_NAME)/bin/pip install -r requirements-2.txt

translations-rescan: 
	# ``Force rescan''.
	$(RM) messages.pot
	$(MAKE) messages.pot

messages.pot:
	$(VENV3)/bin/pybabel extract -F babel.cfg -o messages.pot .

translations-update: translations-update.stamp
translations-update.stamp: messages.pot
	$(BASEDIR)/$(VENV2_NAME)/bin/pybabel update -i messages.pot -d translations
	touch $@

translations-compile: translations-update.stamp
	$(VENV3)/bin/pybabel compile -d translations

tests:
	PYTHONPATH=. $(PYTEST) -vvv tests
