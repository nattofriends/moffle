import re

import pytest
import mock

import line_format

import jinja2.utils

@pytest.mark.parametrize(
    "plain_url, expected_href",
    [
        ("http://www.google.com.", "http://www.google.com"),
        ("http://www.google.com)", "http://www.google.com"),
        ("http://www.google.com'", "http://www.google.com"),
        ("http://www.google.com\"", "http://www.google.com"),
        ("http://www.google.com\x02", "http://www.google.com"),
        ("http://www.google.com\x03", "http://www.google.com"),
        ("\x02http://www.google.com", "http://www.google.com"),
    ],
)
def test_url_patching(plain_url, expected_href):
    html = jinja2.utils.urlize(plain_url)
    href = re.search('href=([\'"])([^\'"]*)[\'"]', html).group(2)

    assert href == expected_href

@mock.patch('re.sub')
@mock.patch('line_format.Markup', side_effect=lambda s: s)
def test_hostmask_tooltip(markup_init, sub):
    replace_marker = "I am a tooltip"
    sub.side_effect = lambda regex, replace, s, count: replace_marker

    line = "[00:00:00] *** Joins test (test@test)"

    result = line_format.hostmask_tooltip(line)

    assert replace_marker in result

@mock.patch('re.sub')
@mock.patch('line_format.Markup', side_effect=lambda s: s)
def test_no_hostmask_no_tooltip(markup_init, sub):
    replace_marker = "I am a tooltip"
    sub.side_effect = lambda regex, replace, s: replace_marker

    line = "[00:00:00] <test> test"

    result = line_format.hostmask_tooltip(line)

    assert replace_marker not in result

@mock.patch('re.sub')
@mock.patch('line_format.Markup', side_effect=lambda s: s)
def test_hostmask_tooltip_escapes_rest(markup_init, sub):
    sub.side_effect = lambda regex, replace, s: s

    line = "[00:00:00] <test> <object object>"

    result = line_format.hostmask_tooltip(line)

    assert "<object object>" not in result
    assert "&lt;" in result
    assert "&gt;" in result
