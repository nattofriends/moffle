import argparse
import re

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from elasticsearch_dsl import Search

import config
import log_path
from util import log


LINE = re.compile(
    r'^\[(?P<time>\d{2}:\d{2}:\d{2})\] (?P<line_type>\* |<|\*\*\* (?:Join|Part|Quit)s: )(?P<author>[^ >]+)>?(?P<text>.+)'
)
TYPE_MAP = {
    '* ': 'action',
    '<': 'normal',
    '*** Joins: ': 'join',
    '*** Parts: ': 'part',
    '*** Quits: ': 'quit',
}


class IndexerAccessControl:
    def evaluate(*args):
        return True


def configure(es, delete_index):
    if es.indices.exists(index='moffle'):
        if delete_index:
            log("Deleting index")
            log(es.indices.delete(index='moffle'))

    else:
        log("Creating index")

        # TODO: define date as date... maybe?
        es.indices.create(
            index='moffle',
            body={
                'mappings': {
                    'logline': {
                        '_all': {'enabled': False},
                        'properties': {
                            'date': {'type': 'keyword'},
                            'time': {'type': 'keyword'},
                            'network': {'type': 'keyword'},
                            'channel': {'type': 'keyword'},
                            'line_no': {'type': 'integer'},
                            'line_type': {'type': 'keyword'},
                        },
                    },
                },
            },
        )


def index_single(es, network, channel, date, lines):
    log("Processing {}/{}/{}".format(network, channel, date))

    # Delete existing
    delete_existing = Search(
        using=es,
        index='moffle',
    ).query(
        "term", network=network,
    ).query(
        "term", channel=channel,
    ).query(
        "term", date=date,
    )

    es.delete_by_query(
        index='moffle',
        body=delete_existing.to_dict(),
    )

    actions = []
    for i, line in lines:
        m = LINE.match(line)
        if not m:
            # What happened here?
            continue

        fields = m.groupdict()
        fields['text'] = fields['text'].strip()
        fields['line_type'] = TYPE_MAP[fields['line_type']]

        fields.update({
            '_index': 'moffle',
            '_type': 'logline',
            'network': network,
            'channel': channel,
            'date': date,
            'line_no': i,
        })
        actions.append(fields)

    if actions:
        log(bulk(es, actions))


def main():
    # TODO: use these parameters
    parser = argparse.ArgumentParser()
    parser.add_argument('--delete-index', action='store_true', help='delete index before indexing')
    parser.add_argument('--start-date', help='index logs with dates after the given date')
    parser.add_argument('--end-date', help='index logs with dates before the given date')
    args = parser.parse_args()

    es = Elasticsearch(config.ES_HOST)
    configure(es, delete_index=args.delete_index)

    paths = getattr(log_path, config.LOG_PATH_CLASS)(IndexerAccessControl())

    for network in paths.networks():
        for channel in paths.channels(network):
            for date in paths.channel_dates(network, channel):
                log = paths.log(network, channel, date)
                index_single(es, network, channel, date, log.log)


if __name__ == "__main__":
    main()
