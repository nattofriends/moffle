import itertools
import statistics
import time

import fastcache
import werkzeug.urls

from werkzeug._compat import text_type, to_native
from werkzeug.urls import _always_safe

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

# Don't look, kids.
werkzeug.urls.url_quote = fastcache.clru_cache(
    maxsize=16384,
)(_url_quote)

werkzeug.urls.url_join = fastcache.clru_cache(
    maxsize=16384,
)(werkzeug.urls.url_join)
