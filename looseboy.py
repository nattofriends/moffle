# -*- coding: utf-8 -*-
import re
from collections import namedtuple
from datetime import datetime
from datetime import timedelta
from itertools import repeat, chain

MatchReplace = namedtuple('MatchReplace', ['matching', 'year', 'month', 'day'])

class LooseDateParser(object):
    """It's gonna be shitty, and you know it."""

    RENDER_FORMAT = "%Y%m%d"
    DATE_SEPARATORS = "-./"
    PREFERRED_DISAMBIGUATION_ORDER = ('month', 'day')

    MONTH_MAX = 12

    WEEKDAYS = (
        'monday',
        'tuesday',
        'wednesday',
        'thursday',
        'friday',
        'saturday',
        'sunday'
    )

    def __init__(self):
        date_cleaners = [
            LooseDateParser._int_cast,
            LooseDateParser._guess_disambiguation,
            LooseDateParser._guess_year,
            LooseDateParser._enrich_year,
        ]

        weekday_cleaners = [
            LooseDateParser._guess_weekday,
        ]

        self.formats = [
            # Literals
            (self.literal("today"), self.render_callable(datetime.now)),
            (self.literal("yesterday"), self.render_callable(LooseDateParser.yesterday)),
            (self.literal("latest"), lambda _: self.latest),

            # Weekdays
            (self.regex(
                "(?P<day>(sun|mon|tues|wednes|thurs|fri|satur|sun)day)",
                weekday_cleaners
                ),
            self.render
            ),

            # Full date
           (self.regex(
                LooseDateParser._make_separated_regex(
                    "(?P<year>\d{2})",
                    "(?P<ambig>\d{2})",
                    "(?P<ambigger>\d{2})",
                ),
                LooseDateParser._prepend_verify_length(6, date_cleaners)
                ),
            self.render
            ),
            (self.regex(
                LooseDateParser._make_separated_regex(
                    "(?P<year>\d{4})",
                    "(?P<ambig>\d{1,2})",
                    "(?P<ambigger>\d{1,2})",
                ),
                date_cleaners
                ),
            self.render
            ),

            # Abbreviated date
            (self.regex(
                LooseDateParser._make_separated_regex(
                    "(?P<ambig>\d{1,2})",
                    "(?P<ambigger>\d{1,2})",
                ),
                date_cleaners
                ),
            self.render
            ),
        ]

    @staticmethod
    def _prepend_verify_length(length, cleaners):
        def verify_length(match_fields):
            if len(match_fields['original']) != length:
                raise ValueError
            return match_fields
        this_cleaner = cleaners[:]
        this_cleaner.insert(0, verify_length)
        return this_cleaner


    @staticmethod
    def yesterday():
        now = datetime.now()
        delta = timedelta(days=1)
        return now - delta

    def literal(self, text):
        def match(input):
            return MatchReplace(text == input, None, None, None)
        return match

    def regex(self, regex, cleaners):
        def match(input):
            result = re.match(regex, input)
            has_match = bool(result)

            if not has_match:
                return MatchReplace(has_match, None, None, None)

            match_fields = result.groupdict()
            match_fields['original'] = input

            try:
                for cleaner in cleaners:
                    match_fields = cleaner(match_fields)
            except ValueError:
                return MatchReplace(False, None, None, None)

            return MatchReplace(
                bool(result),
                year=match_fields['year'],
                month=match_fields['month'],
                day=match_fields['day']
            )

        return match

    @staticmethod
    def _guess_weekday(match_fields):
        now = datetime.now()
        weekday = match_fields['day']
        weekday_index = LooseDateParser.WEEKDAYS.index(weekday)

        days_diff = now.weekday() - weekday_index
        if days_diff < 0:
            days_diff = 7 + days_diff

        delta = timedelta(days=days_diff)
        then = now - delta

        match_fields['year'] = then.year
        match_fields['month'] = then.month
        match_fields['day'] = then.day

        return match_fields

    @staticmethod
    def _int_cast(match_fields):
        # zzz
        for k, v in match_fields.items():
            try:
                v_int = int(v)
                match_fields[k] = v_int
            except ValueError:
                pass
        return match_fields

    @staticmethod
    def _guess_disambiguation(match_fields):
        """Time to do a bit of guessing."""

        def assign(match_fields, sources, targets):
            for source_field, target_field in zip(sources, targets):
                match_fields[target_field] = match_fields[source_field]
            return match_fields

        if match_fields['ambig'] > LooseDateParser.MONTH_MAX:
            order = ('day', 'month')
        else:
            order = LooseDateParser.PREFERRED_DISAMBIGUATION_ORDER

        return assign(match_fields, ('ambig', 'ambigger'), order)

    @staticmethod
    def _guess_year(match_fields):
        if 'year' in match_fields:
            return match_fields

        now = datetime.now()
        if bool(
            (match_fields['month'] == now.month and match_fields['day'] > now.day)
            or match_fields['month'] > now.month
        ):
            match_fields['year'] = now.year - 1
        else:
            match_fields['year'] = now.year

        return match_fields

    @staticmethod
    def _enrich_year(match_fields):
        now = datetime.now()
        century = now.year // 100

        year = match_fields['year']

        if year < 100:
            two_digit = now.year % 100
            decrement = 1 if year > two_digit else 0
            match_fields['year'] = (century - decrement) * 100 + year

        return match_fields

    @staticmethod
    def _make_separated_regex(*components):
        regex_sep = "[{}]?".format(LooseDateParser.DATE_SEPARATORS)
        fountain = repeat(regex_sep)

        return ''.join(list(chain.from_iterable(zip(components, fountain))))

    def render_callable(self, callable):
        def render(match_replace):
            return callable().strftime(self.RENDER_FORMAT)
        return render

    def render(self, match_replace):
        return datetime(
            match_replace.year,
            match_replace.month,
            match_replace.day
        ).strftime(self.RENDER_FORMAT)

    def parse(self, text, latest):
        text = text.lower()
        self.latest = latest

        for matcher, replacer in self.formats:
            match_replace = matcher(text)
            if match_replace.matching:
                return replacer(match_replace)

        return None

