# Moffle

Moffle, the Proceedings of the Internet Relay Chat Preservation Society

## Install

  1. You will need: ``python``, ``virtualenv``, ``nodejs``, ``npm``, ``bower``. Install them however you please. Python 2 and 3 are required.
  2. Install the pythons with ``make install-pythons``.
  3. Roll your own versions of files that end in ``.example``. If you don't into OAuth, some pleb has provided [helpful instruction on how work](https://github.com/kennydo/irc-log-viewer/blob/master/README.rst).
  4. If you so choose, now is the time to set up nginx config for reverse proxy.
  5. Do this:

        bower install
        make init-env
        make css
        make translations-compile
        make

  6. You should now be running a thing. Congratulations.

## Features

  * You can view IRC logs.
  * You can search IRC logs.

## Internationalization

  Moffle supports internationalization using the Flask-Babel extension.

  Because of a limitation of Babel, Python 2 is required to update translation files.

  To rescan source files for new strings, run ``make translations-rescan``.

  To merge new strings into language files, run ``make translations-update``.

  To compile updates language files, run ``make translations-compile``.

### Feature Creep

Bad ideas go here.

  * ACL scope expansion (allow channel #x on network y automatically grants allow on network y)
  * Multi-channel searches (already supported in existing find(1)-based GrepBuilder, easy in LogLine-based GrepBuilder)
  * Tests for line formatting
