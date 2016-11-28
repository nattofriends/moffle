from collections import namedtuple
from copy import copy
from itertools import chain

from flask import session
import fastcache

import config
import util

MAX_PARENT_REFERENCE_RESOLUTION_ROUNDS = 10
CHANNEL_PREFIXES = '#&'
ANY = '*'
PRIVATE_MESSAGE = 'PRIVATE_MESSAGE'

# not used
Rule = namedtuple('Rule', ['verdict', 'user', 'target', 'parent'])

def is_value_rule_value(value, rule_value):
    if rule_value == ANY:
        return True
    if isinstance(rule_value, str):
        return value == rule_value
    else:
        return value in rule_value


class Node:
    TERMINAL_SCOPES = (
        util.Scope.CHANNEL,
        util.Scope.DATE,
    )

    # Most specific to least.
    SCOPE_SPECIFICITY = (
        util.Scope.CHANNEL,
        util.Scope.NETWORK,
        util.Scope.ROOT,
    )

    VERDICT_DISAMBIGUATION = (
        util.Verdict.DENY,
        util.Verdict.ALLOW,
    )

    def __init__(self, verdict, user, scope, value, parent_scope, parent_value):
        self.verdict = verdict
        self.user = user
        self.scope = scope
        self.value = value
        self.parent_scope = parent_scope
        self.parent_value = parent_value
        self.parent = None
        self.children = []

    def add_child(self, child):
        """Try to add the child in the correct place in the tree.
        Return True if successfully parented anywhere, False otherwise.
        """

        if all([
            child.parent_scope == self.scope,
            # TODO: This will not work when the child has a value group
            is_value_rule_value(child.parent_value, self.value),
            # TODO: This will not work when the child has a value group
            self.user in (child.user, ANY),
        ]):
            self.children.append(child)
            child.parent = self
            return True

        else:
            return any([node.add_child(child) for node in self.children])

    def find_rule(self, user, network, channel):
        if is_value_rule_value(user, self.user):
            if self.scope in Node.TERMINAL_SCOPES:
                # This will make more sense once we have date scopes... or
                # something.
                if self.scope == util.Scope.CHANNEL and \
                    (is_value_rule_value(channel, self.value) or \
                     (self.value == PRIVATE_MESSAGE and channel[0] not in CHANNEL_PREFIXES)
                    ):
                    return [self]
                return []
            elif self.scope == util.Scope.NETWORK and is_value_rule_value(network, self.value):
                if channel:
                    return self._ask_children(user, network, channel)
                else:
                    return [self]
            elif self.scope == util.Scope.ROOT:
                return self._ask_children(user, network, channel)
        return []

    def _ask_children(self, user, network, channel):
        result = [child.find_rule(user, network, channel) for child in self.children]
        return filter(
            None,
            chain.from_iterable(result)
        )

    def __repr__(self):
        return "<Node verdict={}, user={}, scope={}, value={}>".format(
            self.verdict,
            self.user,
            self.scope,
            self.value,
        )

    def __str__(self, tree=False, indent=0):
        return "{indent}Node verdict={}, user={}, scope={}, value={}{}".format(
            self.verdict,
            self.user,
            self.scope,
            self.value,
            '\n' + '{spaces}'.join([child.__str__(indent=indent + 1, tree=tree) for child in self.children]).format(spaces='  ' * indent) if tree else '',
            indent='  ' * indent,
        )


class AccessControl:
    # TODO: Enforce scope parent types

    def __init__(self, rules):
        self.rules = Node(None, ANY, util.Scope.ROOT, 'root', util.Scope.ROOT, 'root')

        unresolved_nodes = []

        self.wildcard_nodes = set()

        for rule in rules:
            verdict, user, (target_scope, target_value), (parent_scope, parent_value) = rule
            target = Node(verdict, user, target_scope, target_value, parent_scope, parent_value)

            if target_scope == ANY or target_value == ANY or parent_scope == ANY or parent_value == ANY:
                self.wildcard_nodes.add(target)
            else:
                unresolved_nodes.append(target)

        resolution_rounds = 0
        while True:
            next_unresolved_nodes = []
            for node in unresolved_nodes:
                if not (self.rules.add_child(node)):
                    next_unresolved_nodes.append(node)
            unresolved_nodes = next_unresolved_nodes

            resolution_rounds += 1

            if not unresolved_nodes:
                break

            if resolution_rounds > MAX_PARENT_REFERENCE_RESOLUTION_ROUNDS:
                raise RuntimeError("Spent too much time resolving parent references, probably a node has a non-existent or misspelled parent", unresolved_nodes)

    @property
    def user_email(self):
        user = session.get('user')

        if not user:
            return ''

        return user.get('email')

    def evaluate(self, network, channel):
        return self._evaluate(self.user_email, network, channel)

    @fastcache.clru_cache(maxsize=1024)
    def _evaluate(self, user, network, channel):
        # From the tree.
        applicable = list(self.rules.find_rule(user, network, channel))

        # Add in wildcards.
        # Don't worry about any wildcard scopes right now outside of
        # whether to evaluate it or not; we currently don't
        # have any scopes that can attach to arbitrary other scopes.
        for wildcard_node in self.wildcard_nodes:
            if is_value_rule_value(user, wildcard_node.user):
                if channel:
                    if wildcard_node.scope == util.Scope.NETWORK:
                        # Granting network/anything should have no effect on a
                        # channel decision.
                        pass
                    elif wildcard_node.scope in (util.Scope.CHANNEL, ANY):
                        # Check that our own value is fine.
                        # Then check the parent (a network) to see if it passes
                        # muster.
                        # Wildcard ALLOWs don't apply if the target is actually a private message.
                        if all([
                            (wildcard_node.parent_value in (network, ANY) or wildcard_node.parent_scope == util.Scope.ROOT),
                            any([
                                (wildcard_node.value in (channel, ANY) and (channel[0] in CHANNEL_PREFIXES or wildcard_node.verdict == util.Verdict.DENY)),
                                (wildcard_node.value == PRIVATE_MESSAGE and channel[0] not in CHANNEL_PREFIXES),
                            ]),
                        ]):
                            if wildcard_node.scope == ANY:
                                wildcard_node = copy(wildcard_node)
                                wildcard_node.scope = util.Scope.CHANNEL
                            applicable.append(wildcard_node)
                else:  # No channel, we are being asked to make a decision on a network
                    if wildcard_node.scope == util.Scope.CHANNEL:
                        # We aren't performing scope expansion, so granting
                        # anything on a channel doesn't grant it on its parent
                        # network (which might be interesting behavior).
                        pass
                    elif wildcard_node.scope in (util.Scope.NETWORK, ANY):
                        # Check that the value is right.
                        if wildcard_node.value in (network, ANY):
                            node_copy = copy(wildcard_node)
                            node_copy.scope = util.Scope.NETWORK
                            applicable.append(node_copy)

        # Prefer closest scope, matching user over wildcard
        applicable = sorted(
            applicable,
            key=lambda node: (
                Node.SCOPE_SPECIFICITY.index(node.scope),  # Order by nearest scope,
                node.value == ANY,  # specific target over wildcard,
                node.user == ANY,  # specific user over wildcard,
                Node.VERDICT_DISAMBIGUATION.index(node.verdict),  # Deny over allow
            ),
        )

        assert applicable  # We need at least one...

        rule = applicable[0]
        return rule.verdict == util.Verdict.ALLOW

if __name__ == "__main__":
    ac = AccessControl(config.ACL)

    print(ac._evaluate('chinesedewey@gmail.com', 'yelp', None))
    assert False
    print(ac._evaluate('', 'fbi-network', None))

    print(ac._evaluate('', 'rizon', '#CAA'))
    print(ac._evaluate('', 'channel', '#CAA-staff'))
