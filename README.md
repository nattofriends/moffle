# Moffle

Moffle, the Proceedings of the Internet Relay Chat Preservation Society

## Install

  1. You will need: ``python``, ``virtualenv``, ``nodejs``, ``npm``, ``bower``. Install them however you please.
  2. Create a virtualenv called ``python`` in the directory you cloned Moffle to. Activate the virtualenv and run ``pip install -r requirements.txt``.
  3. Roll your own versions of files that end in ``.example``. If you don't into OAuth, some pleb has provided [helpful instruction on how work](https://github.com/kennydo/irc-log-viewer/blob/master/README.rst).
  4. If you so choose, now is the time to set up nginx config for reverse proxy.
  5. Do this:

        bower install
        make init-env
        make css
        make

  6. You should now be running a thing. Congratulations.

## Features

  * You can view IRC logs.
  * You can search IRC logs.

### Feature Creep

Bad ideas go here.

  * ACL scope expansion (allow channel #x on network y automatically grants allow on network y)
  * Reuse LogLine results for GrepBuilder (find(1) should not be necessary)
  * Date-ranged search after ^
  * AJAX incremental search after ^
  * Multi-channel searches (already supported in existing find(1)-based GrepBuilder, easy in LogLine-based GrepBuilder)
  * Responsive/mobile-friendly interface
