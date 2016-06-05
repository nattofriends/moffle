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
