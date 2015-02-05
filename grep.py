"""Fast grep or something.
"""
from collections import namedtuple
from datetime import date
from datetime import timedelta
from functools import partial
from html import unescape
from itertools import islice
from itertools import groupby
from math import ceil
from math import floor
from multiprocessing import Pool
from os.path import join
from shlex import quote
from statistics import mean
from statistics import StatisticsError
from subprocess import Popen
from subprocess import PIPE
import logging
import re
import signal

import fastcache

import config

logger = logging.getLogger(__name__)


Replacement = namedtuple('Replacement', ['name', 'required', 'regex'])
Hit = namedtuple('Hit', ['channel', 'date', 'begin', 'lines'])
Line = namedtuple('Line', ['channel', 'date', 'line_marker', 'line_no', 'line'])

LINE_REGEX = re.compile("(?P<channel>[#&].*)[_/](?P<date>\d{8})\.log(?P<line_marker>-|:)(?P<line_no>\d+)(?P=line_marker)(?P<line>.*)", re.M)

OUTPUT_PROCESS_CHUNK_SIZE = 32

class GrepBuilder:
    template = """LC_ALL=C xargs -0 grep -in -C {context} {search}"""
    regex = "'<{author}> .*'{query}'.*'"

    author_default = '[^>]*'

    def __init__(self, log_path):
        self.log_path = log_path
        self.context = config.SEARCH_CONTEXT
        self.pool = Pool(config.SEARCH_WORKERS, init_worker)

    def emit(self, channels, network, query, author=None, date_range=None):
        if author:
            author = quote(unescape(author))
        else:
            author = self.author_default

        if date_range:
            date_begin, date_end = date_range
        else:
            date_begin, date_end = None, None

        query = quote(unescape(query))

        regex = self.regex.format(author=author, query=query)
        cmd = self.template.format(context=self.context, search=regex)

        channel_dates = self.log_path.channels_dates(network, channels)
        channel_paths = self._process_channel_dates(channel_dates, network, date_begin, date_end)

        return channel_paths, cmd

    def run(self, *args, **kwargs):
        channel_paths, cmd = self.emit(*args, **kwargs)

        # No-results per worker are still '', so filter them out.
        output = filter(
            None,
            self.pool.map(partial(run_worker, cmd), channel_paths),
        )

        output = '\n--\n'.join(output)

        if not output:
            hits = None
        else:
            hits = self._process_output(output.strip())

            # On int(hit.begin): String sorting strikes again!
            hits.sort(key=lambda hit: (hit.date, int(hit.begin)), reverse=True)

            hits = [list(group) for _, group in groupby(hits, key=lambda hit: hit.date)]

        return hits

    @fastcache.clru_cache(maxsize=16384)
    def _process_output(self, output):
        splits = output.split('\n--\n')

        return self.pool.map(_process_hit, splits, chunksize=OUTPUT_PROCESS_CHUNK_SIZE)

    def _process_channel_dates(self, channel_dates, network, date_begin, date_end):
        def next_chunk_size(chunk_sizes, target_chunk_size):
            """Allocate fair chunk sizes (instead of just ceiling all the time).
            This avoids the leftover guy who only has one path. This is bad
            because then grep doesn't output the filename and we then have no way of finding
            it out.
            """

            try:
                average_chunk_size = mean(chunk_sizes)
            except StatisticsError:
                average_chunk_size = 0

            if average_chunk_size < target_chunk_size:
                chunk_size = ceil(target_chunk_size)
            else:
                chunk_size = floor(target_chunk_size)

            return chunk_size

        def fold_chunks(chunks):
            """Even after fair chunking, if there are too many workers and not enough
            paths to process, there could still be chunks with only one path to process.
            In this case, just fold the chunk in to a neighbor.
            """
            chunks_folded = chunks[:1]

            for elem in chunks[1:]:
                if len(elem) == 1:
                    chunks_folded[-1].extend(elem)
                else:
                    chunks_folded.append(elem)
            if len(chunks_folded) > 1 and len(chunks_folded[0]) == 1:
                chunks_folded[1] == chunks_folded[0] + chunks_folded[1]
                del chunks_folded[0]

            return chunks_folded

        filtered_channel_dates = []

        for log in channel_dates:
            date = log['date_obj']

            if ((date_begin and date_begin < date) or (not date_begin)) and \
                ((date_end and date_end >= date) or (not date_end)):
                filtered_channel_dates.append(log)

        channel_paths = [join(
            self.log_path.network_to_path(network),
            log['filename'],
        ) for log in filtered_channel_dates]

        channel_paths.sort()

        target_chunk_size = len(channel_paths) / config.SEARCH_WORKERS
        chunk_sizes = []

        paths_it = iter(channel_paths)
        chunks = []

        while True:
            chunk_size = next_chunk_size(chunk_sizes, target_chunk_size)

            chunk = list(islice(paths_it, chunk_size))
            if not chunk:
                break

            chunk_sizes.append(chunk_size)
            chunks.append(chunk)

        chunks = fold_chunks(chunks)

        channel_paths = ['\0'.join(chunk).encode() for chunk in chunks]

        return channel_paths

    def max_segment(self, oldest):
        today = date.today()
        total_interval = today - oldest
        max_segment = floor(total_interval / timedelta(weeks=config.SEARCH_CHUNK_INTERVAL_WEEKS))

        return max_segment

    def segment_bounds(self, segment):
        today = date.today()
        chunk_size = timedelta(weeks=config.SEARCH_CHUNK_INTERVAL_WEEKS)
        date_end = today - chunk_size * segment
        date_start = date_end - chunk_size

        return date_start, date_end


def init_worker():
    signal.signal(signal.SIGINT, signal.SIG_IGN)

def run_worker(cmd, paths):
    proc = Popen(cmd, shell=True, stdout=PIPE, stdin=PIPE)
    output, _ = proc.communicate(paths)
    output = output.decode('utf-8', errors='ignore').strip()

    return output

def _process_hit(split):
    lines = split.strip().split('\n')

    channel, date, begin = None, None, None
    line_objs = []

    for line in lines:
        m = LINE_REGEX.search(line)

        # For line continuations
        if not m:
            if not line_objs:
                continue

            last = line_objs[-1]
            line_objs[-1] = last._replace(line=last.line + '\n' + line)
            continue

        line = Line(**m.groupdict())

        if not channel:
            channel = line.channel
            date = line.date
            begin = line.line_no

        line_objs.append(line)

    return Hit(channel, date, begin, line_objs)
