"""Fast grep or something.
"""
from collections import namedtuple
from functools import wraps
from itertools import groupby
from os.path import expanduser
from os.path import expandvars
from subprocess import CalledProcessError
from subprocess import check_output
import logging
import re

import cachetools

logger = logging.getLogger(__name__)


Replacement = namedtuple('Replacement', ['name', 'required', 'regex'])
Hit = namedtuple('Hit', ['channel', 'date', 'begin', 'lines'])
Line = namedtuple('Line', ['channel', 'date', 'line_marker', 'line_no', 'line'])


class GrepBuilder:
    """Since we're calling it ``Builder'', let's go with chained construction, as tired of a Java idiom as that may be.
    """
    template = """find {path} -type f -regextype posix-extended -iregex '{channels}' -print0 | LC_ALL=C xargs -0 grep -in -C {context} '{search}' || true"""
    regex = "<{author}> .*{search}.*"

    defaults = {
        'context': 4,
    }

    regex_defaults = {
        'author': '[^>]*',
    }

    other_replacements = [
        Replacement('path', required=True, regex=False),
        Replacement('channels', required=True, regex=False),
        Replacement('search', required=True, regex=True),
    ]

    LINE_REGEX = re.compile("(?P<channel>[#&].*)[_/](?P<date>\d{8})\.log(?P<line_marker>-|:)(?P<line_no>\d+)(?P=line_marker)(?P<line>.*)", re.M)

    def __init__(self):
        self.frozen = False
        self.params = self.defaults.copy()
        self.regex_params = self.regex_defaults.copy()

        self.replacements = self.other_replacements.copy()
        for replacement in self.defaults:
            self.replacements.append(Replacement(replacement, required=False, regex=False))
        for replacement in self.regex_defaults:
            self.replacements.append(Replacement(replacement, required=False, regex=True))

    clear = __init__

    def freeze(self):
        self.frozen = True

    def chaining(f):
        """Do not worry about what is going on here.
        """
        @wraps(f)
        def wrapper(self, *args, **kwargs):
            f(self, *args, **kwargs)
            return self
        return wrapper

    @chaining
    def channels(self, channels):
        self.channels = ".*({}).*".format("|".join(["{}[_/]".format(ch) for ch in channels]))

    @chaining
    def authors(self, authors):
        self.author = "|".join(authors)

    @chaining
    def dir(self, directory):
        self.path = expandvars(expanduser(directory))

    def __getattr__(self, name):
        if self.frozen:
            return self.__dict__[name]
        else:
            def simple_builder(value):
                setattr(self, name, value)
                return self
            return simple_builder

    def emit(self):
        self.freeze()

        regex_params = self.regex_defaults.copy()
        params = self.defaults.copy()

        for replacement in self.replacements:
            try:
                val = getattr(self, replacement.name)

                if replacement.regex:
                    regex_params[replacement.name] = val
                else:
                    params[replacement.name] = val
            except KeyError as ex:
                if replacement.required:
                    raise Exception("Missing required parameters {}".format(ex.args)) from None

        params.update(search=self.regex.format(**regex_params))
        return self.template.format(**params)

    def run(self):
        cmd = self.emit()

        output = check_output(cmd, shell=True).decode('utf-8', errors='ignore').strip()

        if not output:
            hits = None
        else:
            hits = self._process_output(output.strip())

            # On int(hit.begin): String sorting strikes again!
            hits.sort(key=lambda hit: (hit.date, int(hit.begin)), reverse=True)

            hits = [list(group) for _, group in groupby(hits, key=lambda hit: hit.date)]

        self.clear()

        return hits


    @cachetools.lru_cache(maxsize=16384)
    def _process_output(self, output):
        splits = output.split('\n--\n')
        return [self._process_hit(split.strip()) for split in splits]

    def _process_hit(self, split):
        lines = split.split('\n')

        channel, date, begin = None, None, None
        line_objs = []

        for line in lines:
            m = self.LINE_REGEX.search(line)

            if not m:
                if not line_objs:
                    continue

                last = line_objs[-1]
                line_objs[-1] = last._replace(line=last.line + '\n' + line)
                continue

            line = Line(**m.groupdict())

            # If we have no data, this is the first line.
            # So set the hit metadata.
            if not channel:
                channel = line.channel
                date = line.date
                begin = line.line_no

            line_objs.append(line)

        return Hit(channel, date, begin, line_objs)


if __name__ == "__main__":
    grep = GrepBuilder() \
        .channels(["CAA-staff"]) \
        .dir("/home/znc/.znc/users/rizon/moddata/log") \
        .search("dodko")

    print(grep.emit())
    grep.run()
