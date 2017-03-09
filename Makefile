# Makefile for uwsgi, because uwsgi sux

# App-specific config

include Makefile.appconfig

APP_MODULE = "app:create()"
PIDFILE = app.pid
VENV_NAME = runtime
UWSGI_LOG = uwsgi.log

# None of your business

BASEDIR = $(shell readlink -f .)
PIDPATH = $(BASEDIR)/$(PIDFILE)
VENV = $(BASEDIR)/$(VENV_NAME)
BIN = $(VENV)/bin/uwsgi

RM = rm -f

ifeq ($(shell which py.test),)
	PYTEST = $(VENV)/bin/py.test
else
	PYTEST = $(shell which py.test)
endif

.PHONY: clean tests translations-rescan translations-update translations-compile

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
	$(RM) static/style.css
	$(RM) static/_bootstrap_version.scss
	$(RM) messages.pot
	$(RM) *.stamp

last-exception:
	@sed -nE '/^Traceback/,/^\[pid: /p' $(UWSGI_LOG) | tac | sed '/^Traceback/q' | tac

css: static/style.css

static/_bootstrap_version.scss: static/vendor/bootstrap-sass-official/bower.json
	echo "\$$bower-bootstrap-version:" \"$(shell cat static/vendor/bootstrap-sass-official/bower.json | jq -r .version)\" > static/_bootstrap_version.scss

static/style.css: static/style.scss static/_bootstrap_version.scss static/vendor/bootstrap-sass-official/assets/stylesheets/_bootstrap.scss
	$(VENV)/bin/sassc -t compressed static/style.scss static/style.css

init-env:
	ln -s ../bower_components static/vendor

init-python:
	virtualenv --python=python3 --no-site-packages $(VENV_NAME)
	$(VENV)/bin/pip install -r requirements.txt

translations-rescan:
	# ``Force rescan''.
	$(RM) messages.pot
	$(MAKE) messages.pot

messages.pot:
	$(VENV)/bin/pybabel extract -F babel.cfg -o messages.pot .

translations-update: translations-update.stamp
translations-update.stamp: messages.pot
	$(VENV)/bin/pybabel update -i messages.pot -d translations
	touch $@

translations-compile: translations-update.stamp
	$(VENV)/bin/pybabel compile -d translations

tests:
	PYTHONPATH=. $(PYTEST) -vvv tests
