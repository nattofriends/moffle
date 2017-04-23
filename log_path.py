# -*- coding: utf-8 -*-
from collections import namedtuple
from datetime import date
from operator import itemgetter
from itertools import chain
import os
import re

from natsort import natsorted
from natsort import ns
import cachetools
import fastcache

import config
import exceptions
import looseboy
import util

LOG_INTERMEDIATE_BASE = "moddata/log"
LOG_FILENAME_REGEX = re.compile("(?P<filename>(?P<network>(default|znc)+)_(?P<channel>[#&]*[a-zA-Z0-9\u4e00-\u9fff/_\-\.\?\$]+)_(?P<date>\d{8})\.log)")

LogResult = namedtuple('LogResult', ['log', 'before', 'after'])

ldp = looseboy.LooseDateParser()


@fastcache.clru_cache(maxsize=1024)
def parse_date(date_string):
    if len(date_string) == 8:
        components = date_string[0:4], date_string[4:6], date_string[6:8]
    elif len(date_string) == 10:
        components = date_string[0:4], date_string[5:7], date_string[8:10]

    components = map(int, components)
    return date(*components)


class LogPath:

    def __init__(self, ac):
        self.ac = ac

    def networks(self):
        base_contents = os.listdir(config.LOG_BASE)

        dirs = [
            network for network in base_contents
            if os.path.isdir(
                self.network_to_path(network)
            ) and self.ac.evaluate(network, None)
        ]

        return sorted(dirs)

    def channels(self, network):
        matches = self._channels_list(network)

        # This network doesn't actually exist.
        if matches is None:
            raise exceptions.NoResultsException()

        channels = natsorted(
            {
                filename['channel']
                for filename in matches
                if self.ac.evaluate(network, filename['channel'])
            },
            alg=ns.G | ns.LF,
        )

        if not channels:
            raise exceptions.NoResultsException()

        return channels

    def channel_dates(self, network, channel):
        matches = self._channels_list(network)

        if matches is None:
            raise exceptions.NoResultsException()

        if not self.ac.evaluate(network, channel):
            raise exceptions.NoResultsException()

        try:
            self._maybe_channel(network, channel, matches)
        except (
            exceptions.NoResultsException,
            exceptions.MultipleResultsException,
            exceptions.CanonicalNameException,
        ):
            raise

        dates = [filename['date'] for filename in matches if filename['channel'] == channel]

        return sorted(dates, reverse=True)

    def channels_dates(self, network, channels):
        """For search use.
        Further filtering will be performed on the search side.
        """
        matches = self._channels_list(network)

        if matches is None:
            raise exceptions.NoResultsException()

        # This behavior is slightly different from elsewhere.
        channels = [ch for ch in channels if self.ac.evaluate(network, ch)]

        files = [filename for filename in matches if filename['channel'] in channels]

        return sorted(files, key=itemgetter('date_obj'), reverse=True)

    def log(self, network, channel, date):
        matches = self._channels_list(network)

        if matches is None:
            raise exceptions.NoResultsException()

        if not self.ac.evaluate(network, channel):
            raise exceptions.NoResultsException()

        try:
            self._maybe_channel(network, channel, matches)
        except (
            exceptions.NoResultsException,
            exceptions.MultipleResultsException,
            exceptions.CanonicalNameException,
        ):
            raise

        channel_files = [filename for filename in matches if filename['channel'] == channel]
        channel_files = sorted(channel_files, key=itemgetter('date'))

        latest = channel_files[-1]['date']

        parsed_date = ldp.parse(date, latest)
        if not parsed_date:
            raise exceptions.NoResultsException()
        elif parsed_date != date:
            raise exceptions.CanonicalNameException(util.Scope.DATE, parsed_date)

        log = [filename for filename in channel_files if filename['date'] == date]

        if len(log) == 0:
            raise exceptions.NoResultsException()

        log = log[0]
        log_idx = channel_files.index(log)

        before, after = None, None
        if log_idx > 0:
            before = channel_files[log_idx - 1]['date']
        if log_idx < len(channel_files) - 1:
            after = channel_files[log_idx + 1]['date']

        log_path = os.path.join(self.network_to_path(network), log['filename'])

        # Enumerate at 1: these are log line numbers.
        log_file = enumerate(open(log_path, errors='ignore').readlines(), start=1)

        return LogResult(log_file, before, after)

    @fastcache.clru_cache(maxsize=128)
    def network_to_path(self, network):
        return os.path.join(config.LOG_BASE, network, LOG_INTERMEDIATE_BASE)

    def _maybe_channel(self, network, channel, matches):
        # This looks a bit intensive.
        # Accomodate partial matches to see if containing-match only matches
        # one channel. If it does, we can 302 to the real URL, but otherwise
        # we should 404.
        maybe_channels = {filename['channel'] for filename in matches if channel.lower() in filename['channel'].lower()}

        # Bail if it's ambiguous...
        if len(maybe_channels) > 1:
            # unless one of them is an exact match.
            exact = [maybe_channel for maybe_channel in maybe_channels if maybe_channel == channel]
            if len(exact) != 1:
                raise exceptions.MultipleResultsException()
        elif len(maybe_channels) == 1:
            canonical_channel = list(maybe_channels)[0]

            if channel != canonical_channel:
                raise exceptions.CanonicalNameException(util.Scope.CHANNEL, canonical_channel)
        elif len(maybe_channels) == 0:
            # We have nothing. It is unfortunate.
            raise exceptions.NoResultsException()

    def _channels_list(self, network):
        channel_base = self.network_to_path(network)

        if not os.path.exists(channel_base):
            return None

        files = os.listdir(channel_base)

        file_matches = [LOG_FILENAME_REGEX.match(filename) for filename in files]
        file_matches = [match.groupdict() for match in file_matches if match is not None]

        for match in file_matches:
            match['date_obj'] = parse_date(match['date'])

        return file_matches


class DirectoryDelimitedLogPath(LogPath):
    LOG_SUFFIX = '.log'

    def channel_dates(self, network, channel):
        dates = self._dates_list(network, channel)

        if not dates:
            raise exceptions.NoResultsException()

        if not self.ac.evaluate(network, channel):
            raise exceptions.NoResultsException()

        dates = [x['date'] for x in dates]
        return sorted(dates, reverse=True)

    def channels_dates(self, network, channels):
        """
        For search use. Further filtering will be performed on the search side.
        """
        matches = self._channels_list(network)

        if matches is None:
            raise exceptions.NoResultsException()

        # This behavior is slightly different from elsewhere.
        channels = [ch for ch in channels if self.ac.evaluate(network, ch)]

        files = chain.from_iterable([self._dates_list(network, ch) for ch in channels])

        return sorted(files, key=itemgetter('date_obj'), reverse=True)

    def log(self, network, channel, date):
        channels = self._channels_list(network)
        dates = self._dates_list(network, channel)

        if channels is None or dates is None:
            raise exceptions.NoResultsException()

        if not self.ac.evaluate(network, channel):
            raise exceptions.NoResultsException()

        try:
            self._maybe_channel(network, channel, channels)
        except (
            exceptions.NoResultsException,
            exceptions.MultipleResultsException,
            exceptions.CanonicalNameException,
        ):
            raise

        latest = max(dates, key=itemgetter('date'))['date']

        parsed_date = ldp.parse(date, latest)
        if not parsed_date:
            raise exceptions.NoResultsException()
        elif parsed_date != date:
            raise exceptions.CanonicalNameException(util.Scope.DATE, parsed_date)

        # Reverse the human-friendly ordering here.
        channel_dates = self.channel_dates(network, channel)[::-1]
        log = [log_date for log_date in channel_dates if log_date == date]

        if len(log) == 0:
            raise exceptions.NoResultsException()

        log = log[0]
        log_idx = channel_dates.index(log)

        before, after = None, None
        if log_idx > 0:
            before = channel_dates[log_idx - 1]
        if log_idx < len(channel_dates) - 1:
            after = channel_dates[log_idx + 1]

        log_path = os.path.join(self.channel_to_path(network, channel),
                                log + DirectoryDelimitedLogPath.LOG_SUFFIX)

        log_file = enumerate(open(log_path, errors='ignore').readlines(), start=1)

        return LogResult(log_file, before, after)

    # This lets us use LogPath.networks instead of reimplementing.
    @fastcache.clru_cache(maxsize=128)
    def network_to_path(self, network):
        return os.path.join(config.LOG_BASE, network)

    @fastcache.clru_cache(maxsize=128)
    def channel_to_path(self, network, channel):
        return os.path.join(self.network_to_path(network), channel)

    # This lets us use LogPath.channels instead of reimplementing.
    @cachetools.ttl_cache(maxsize=128, ttl=21600)
    def _channels_list(self, network):
        network_base = self.network_to_path(network)

        if not os.path.exists(network_base):
            return None

        files = os.listdir(network_base)
        files = [{'channel': channel} for channel in files]

        return files

    def _dates_list(self, network, channel):
        channel_base = self.channel_to_path(network, channel)

        if not os.path.exists(channel_base):
            return None

        files = os.listdir(channel_base)
        files = [{
            'channel': channel,
            'date': filename[:-1 * len(DirectoryDelimitedLogPath.LOG_SUFFIX)],
            'filename': os.path.join(channel_base, filename)
        } for filename in files if filename.endswith(DirectoryDelimitedLogPath.LOG_SUFFIX)]

        for f in files:
            f['date_obj'] = parse_date(f['date'])

        return files


class ZNC16DirectoryDelimitedLogPath(DirectoryDelimitedLogPath):
    # Assume people are creating user-per-network. If they aren't they can subclass
    # something themselves. This assumption is embedded into LOG_FILENAME_REGEX
    # anyway.
    NETWORK_DEFAULT_USER = "default"

    @fastcache.clru_cache(maxsize=128)
    def network_to_path(self, network):
        return os.path.join(config.LOG_BASE, network, LOG_INTERMEDIATE_BASE, ZNC16DirectoryDelimitedLogPath.NETWORK_DEFAULT_USER)

    def _dates_list(self, network, channel):
        """ZNC 1.6 default stores files with a %Y-%m-%d format. Preserve the %Y%m%d format in display
        by coercing it back and forth every single time. Performance impact: yet to determined
        """

        files = super(ZNC16DirectoryDelimitedLogPath, self)._dates_list(network, channel)

        if not files:
            return files

        for f in files:
            f['date'] = f['date_obj'].strftime("%Y%m%d")

        return files

    def log(self, network, channel, date):
        channels = self._channels_list(network)
        dates = self._dates_list(network, channel)

        if channels is None or dates is None:
            raise exceptions.NoResultsException()

        if not self.ac.evaluate(network, channel):
            raise exceptions.NoResultsException()

        try:
            self._maybe_channel(network, channel, channels)
        except (
            exceptions.NoResultsException,
            exceptions.MultipleResultsException,
            exceptions.CanonicalNameException,
        ):
            raise

        latest = max(dates, key=itemgetter('date'))['date']

        parsed_date = ldp.parse(date, latest)
        if not parsed_date:
            raise exceptions.NoResultsException()
        elif parsed_date != date:
            raise exceptions.CanonicalNameException(util.Scope.DATE, parsed_date)

        # Reverse the human-friendly ordering here.
        channel_dates = self.channel_dates(network, channel)[::-1]
        log = [log_date for log_date in channel_dates if log_date == date]

        if len(log) == 0:
            raise exceptions.NoResultsException()

        log = log[0]
        log_idx = channel_dates.index(log)

        # Convert the no-dash presentation date...
        log = log[0:4] + '-' + log[4:6] + '-' + log[6:8]

        before, after = None, None
        if log_idx > 0:
            before = channel_dates[log_idx - 1]
        if log_idx < len(channel_dates) - 1:
            after = channel_dates[log_idx + 1]

        log_path = os.path.join(self.channel_to_path(network, channel),
                                log + DirectoryDelimitedLogPath.LOG_SUFFIX)

        log_file = enumerate(open(log_path, errors='ignore').readlines(), start=1)

        return LogResult(log_file, before, after)
