from collections import namedtuple
import re

from flask import session
import cachetools

import config

Rule = namedtuple('Rule', ['verdict', 'user', 'scope', 'target'])


class AccessControl:

    def __init__(self, rules):
        self.rules = []

        for rule in rules:
            self.rules.append(Rule(*rule))

    @property
    def user_email(self):
        user = session.get('user')

        if not user:
            return ''

        return user.get('email')

    def evaluate(self, scope, target):
        return self._evaluate(self.user_email, scope, target)

    @cachetools.lru_cache(maxsize=256)
    def _evaluate(self, user, scope, target):
        # Which of the rules apply to this user?
        applicable = []
        for rule in self.rules:
            if rule.user == user or rule.user == '*':
                applicable.append(rule)

        # Which of the rules apply to this scope?
        filtering = []
        for rule in applicable:
            if rule.scope == scope or rule.scope == '*':
                filtering.append(rule)
        applicable = filtering

        # Which of the rules apply to this target?
        filtering = []
        for rule in applicable:
            if rule.target == target or rule.target == '*' or re.match('^' + rule.target + '$', target):
                filtering.append(rule)
        applicable = filtering

        # Prefer whitelist. "allow" comes before "deny"
        applicable = sorted(applicable, key=lambda rule: rule.verdict)

        return applicable[0].verdict == 'allow'

if __name__ == "__main__":
    ac = AccessControl(config.ACL)

    print(ac.evaluate('', 'network', 'fbi-network'))

    print(ac.evaluate('', 'network', 'rizon'))
    print(ac.evaluate('', 'channel', '#CAA'))
    print(ac.evaluate('', 'channel', '#CAA-staff'))
