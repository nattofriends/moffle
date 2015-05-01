import itertools

import fastcache
import jinja2.utils
import werkzeug.urls

from werkzeug._compat import text_type, to_native
from werkzeug.urls import _always_safe

from jinja2.utils import (
    _digits,
    _letters,
    _punctuation_re,
    _simple_email_re,
    _word_split_re,
    escape,
    text_type,
)

import util

def _get_stringy_set(seq, charset, errors):
    if isinstance(seq, text_type):
        seq = seq.encode(charset, errors)
    return bytearray(seq)

_cached_get_stringy_set = fastcache.clru_cache()(_get_stringy_set)

def _upstream_transform(string, safe):
    rv = bytearray()

    for char in bytearray(string):
        if char in safe:
            rv.append(char)
        else:
            rv.extend(('%%%02X' % char).encode('ascii'))

    return rv

def _chunking_transform(string, safe):
    string_bytes = bytearray(string)
    safe_chars = [char in safe for char in string_bytes]
    safe_count = sum(safe_chars)
    unsafe_count = (len(string_bytes) - safe_count) * 3

    rle = [(val, len(list(group))) for val, group in itertools.groupby(safe_chars)]

    rv = bytearray(safe_count + unsafe_count)
    src_pos, dst_pos = (0, 0)
    for val, length in rle:
        if val:
            rv[dst_pos:dst_pos + length] = string_bytes[src_pos:src_pos + length]
            dst_pos += length
        else:
            rv[dst_pos:dst_pos + length * 3] = b''.join(map(lambda ch: ('%%%02X' % ch).encode('ascii'), string_bytes[src_pos:src_pos + length]))
            dst_pos += length * 3
        src_pos += length

    return rv

_get_stringy_set_impl = _get_stringy_set
_transform_impl = _upstream_transform

_get_stringy_set_impl = _cached_get_stringy_set
# _transform_impl = _chunking_transform

def _url_quote(string, charset='utf-8', errors='strict', safe='/:', unsafe=''):
    """URL encode a single string with a given encoding.

    :param s: the string to quote.
    :param charset: the charset to be used.
    :param safe: an optional sequence of safe characters.
    :param unsafe: an optional sequence of unsafe characters.

    .. versionadded:: 0.9.2
       The `unsafe` parameter was added.
    """
    if not isinstance(string, (text_type, bytes, bytearray)):
        string = text_type(string)
    if isinstance(string, text_type):
        string = string.encode(charset, errors)

    safe = _get_stringy_set_impl(safe, charset, errors)
    unsafe = _get_stringy_set_impl(unsafe, charset, errors)

    safe = frozenset(safe + _always_safe) - frozenset(unsafe)
    rv = _transform_impl(string, safe)
    return to_native(bytes(rv))


@util.delay_template_filter('cached_urlize')
def urlize(text, trim_url_limit=None, nofollow=False):
    """Converts any URLs in text into clickable links. Works on http://,
    https:// and www. links. Links can have trailing punctuation (periods,
    commas, close-parens) and leading punctuation (opening parens) and
    it'll still do the right thing.

    If trim_url_limit is not None, the URLs in link text will be limited
    to trim_url_limit characters.

    If nofollow is True, the URLs in link text will get a rel="nofollow"
    attribute.
    """

    words = _word_split_re.split(text_type(escape(text)))
    nofollow_attr = nofollow and ' rel="nofollow"' or ''

    for i, word in enumerate(words):
        replace = _urlize_parse(word, nofollow_attr, trim_url_limit)
        if replace:
            words[i] = replace
    return u''.join(words)

def trim_url(x, limit):
    return limit is not None \
        and (x[:limit] + (len(x) >= limit and '...' or '')) or x


_ligits = _letters + _digits
_domains = ('.com', '.net', '.org', '.jp',)

@fastcache.clru_cache(maxsize=16384)
def _urlize_parse(word, nofollow_attr, trim_url_limit):
    match = _punctuation_re.match(word)
    if match:
        changed = False
        lead, middle, trail = match.groups()
        if middle.startswith('www.') or (
            '@' not in middle and
            not middle.startswith(('http://', 'https://')) and
            len(middle) > 0 and
            middle[0] in _ligits and
            middle.endswith(_domains)
            ):
            middle = '<a href="http://%s"%s>%s</a>' % (middle,
                nofollow_attr, trim_url(middle, trim_url_limit))
            changed = True
        elif middle.startswith(('http://', 'https://')):
            middle = '<a href="%s"%s>%s</a>' % (middle,
                nofollow_attr, trim_url(middle, trim_url_limit))
            changed = True
        elif '@' in middle and not middle.startswith('www.') and \
            not ':' in middle and _simple_email_re.match(middle):
            middle = '<a href="mailto:%s">%s</a>' % (middle, middle)
            changed = True

        if changed:
            return lead + middle + trail

# Don't look, kids.
werkzeug.urls.url_quote = fastcache.clru_cache(
    maxsize=16384,
)(_url_quote)

werkzeug.urls.url_join = fastcache.clru_cache(
    maxsize=16384,
)(werkzeug.urls.url_join)
