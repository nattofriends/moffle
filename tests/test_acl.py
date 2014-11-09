from collections import OrderedDict
import pytest

from acl import AccessControl

TEST_INTEGRATION_INPUTS = OrderedDict((
    (
        "default deny",
        (
            (
                ('deny', '*', ('*', '*'), ('root', 'root')),
            ),
            'test@example.com', 'net', '#channel',
            False,
        ),
    ),
    (
        "allow user named network",
        (
            (
                ('deny', '*', ('*', '*'), ('root', 'root')),
                ('allow', 'test@example.com', ('network', 'net'), ('root', 'root')),
            ),
            'test@example.com','net', None,
            True,
        ),
    ),
    (
        "allow user named network and channel",
        (
            (
                ('deny', '*', ('*', '*'), ('root', 'root')),
                ('allow', 'test@example.com', ('network', 'net'), ('root', 'root')),
                ('allow', 'test@example.com', ('channel', '#channel'), ('network', 'net')),
            ),
            'test@example.com','net', '#channel',
            True,
        ),
    ),
    (
        "allow user named network does not grant channel",
        (
            (
                ('deny', '*', ('*', '*'), ('root', 'root')),
                ('allow', 'test@example.com', ('network', 'net'), ('root', 'root')),
            ),
            'test@example.com', 'net', '#channel',
            False,
        ),
    ),
    (
        "allow user named channel does not grant network",
        (
            (
                ('deny', '*', ('*', '*'), ('root', 'root')),
                ('allow', 'test@example.com', ('channel', '#channel'), ('root', 'root')),
            ),
            'test@example.com', 'net', None,
            False,
        ),
    ),
    (
        "deny user named network to other user",
        (
            (
                ('deny', '*', ('*', '*'), ('root', 'root')),
                ('allow', 'test@example.com', ('network', 'net'), ('root', 'root')),
            ),
            'test2@example.com', 'net', None,
            False,
        ),
    ),
    (
        "deny user named network to other network",
        (
            (
                ('deny', '*', ('*', '*'), ('root', 'root')),
                ('allow', 'test@example.com', ('network', 'net'), ('root', 'root')),
            ),
            'test@example.com', 'othernet', None,
            False,
        ),
    ),
    (
        "deny user channel on named network to other network",
        (
            (
                ('deny', '*', ('*', '*'), ('root', 'root')),
                ('allow', 'test@example.com', ('network', 'net'), ('root', 'root')),
                ('allow', 'test@example.com', ('channel', '#channel'), ('network', 'net')),
            ),
            'test@example.com', 'othernet', '#channel',
            False,
        ),
    ),
    (
        "allow wildcard network fixed user",
        (
            (
                ('deny', '*', ('*', '*'), ('root', 'root')),
                ('allow', 'test@example.com', ('network', '*'), ('root', 'root')),
            ),
            'test@example.com', 'net', None,
            True,
        ),
    ),
    (
        "deny wildcard network wildcard user",
        (
            (
                ('deny', '*', ('*', '*'), ('root', 'root')),
                ('allow', '*', ('network', '*'), ('root', 'root')),
            ),
            'test@example.com', 'net', None,
        False,
        ),
    ),
    (
        "allow wildcard wildcard scope fixed user access network",
        (
            (
                ('deny', '*', ('*', '*'), ('root', 'root')),
                ('allow', 'test@example.com', ('*', '*'), ('root', 'root')),
            ),
            'test@example.com', 'net', None,
            True,
        ),
    ),
    (
        "allow wildcard wildcard scope fixed user access channel",
        (
            (
                ('deny', '*', ('*', '*'), ('root', 'root')),
                ('allow', 'test@example.com', ('*', '*'), ('root', 'root')),
            ),
            'test@example.com', 'net', '#channel',
            True,
        ),
    ),

))

@pytest.mark.parametrize(
    "rules, email, network, channel, expected",
    TEST_INTEGRATION_INPUTS.values(),
    ids=list(TEST_INTEGRATION_INPUTS.keys()),
)
def test_integration(rules, email, network, channel, expected):
    ac = AccessControl(rules)
    assert ac._evaluate(email, network, channel) == expected
