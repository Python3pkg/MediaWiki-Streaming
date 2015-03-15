"""
Mends revision diffs.  This script will take a sequence of revisions with diff
information that were generated in blocks and mend the missing diff information
at the block seams.  This utility is useful when used in conjunction with
json2diffs in in a hadoop setting with json2diffs as the mapper and mend_diffs
as the reducer.

Usage:
    mend_diffs (-h|--help)
    mend_diffs --config=<path> [--drop-text] [--timeout=<secs>]
                               [--verbose]

Options:
    --config=<path>        The path to difference detection configuration
    --drop-text            Drops the 'text' field from the JSON blob
    --timeout=<secs>       The maximum time a diff can run in seconds before
                           being cancelled.  [default: <infinity>]
    --namespaces=<ns>      A comma separated list of page namespaces to be
                           processed [default: <all>]
    --verbose              Print out progress information
"""
import sys
from itertools import groupby

import docopt
from more_itertools import peekable

from .json2diffs import diff_revisions


def main(argv=None):
    args = docopt.docopt(__doc__, argv=argv)

    config_doc = yamlconf.load(open(args['--config']))
    diff_engine = DiffEngine.from_config(config_doc, config_doc["diff_engine"])

    drop_text = bool(args['--drop-text'])

    if args['--timeout'] == "<infinity>":
        timeout = None
    else:
        timeout = float(args['--timeout'])

    verbose = bool(args['--verbose'])

    run(read_docs(sys.stdin), diff_engine, timeout, drop_text, verbose)

def run(diff_docs, diff_engine, timeout, drop_text, verbose):

    for mended_doc in mend_diffs(diff_docs):
        if drop_text:
            del mended_doc['text']

        json.dump(diff_doc, sys.stdout)
        sys.stdout.write("\n")

def mend_diffs(revision_docs, diff_engine, timeout=None, drop_text=False,
               verbose=False):

    page_revision_docs = groupby(revision_docs,
                                 key=lambda r:r['page']['title'])

    for page_title, revision_docs in page_revision_docs:

        revision_docs = peekable(revision_docs)

        while revision_docs.peek(None) is not None:

            revision_doc = next(revision_docs)

            if 'text' not in revision_doc:
                raise RuntimeError("Revision documents must contain a 'text' " +
                                   "field for mending.")
            elif 'diff' not in revision_doc:
                raise RuntimeError("Revision documents must contain a 'diff' " +
                                   "field for mending.")

            yield revision_doc

            # Check if we're going to need to mend
            if revision_docs.peek()['diff']['last_id'] != revision_doc['id']:
                processor = diff_engine.processor(last_text=revision_doc['text'])

                broken_docs = read_broken_docs(revision_docs)
                mended_docs = diff_revisions(broken_docs, processor,
                                             last_id=revision_doc['id'],
                                             timeout=timeout)

                for mended_doc in mended_docs:
                    yield mended_doc


def read_broken_docs(revision_docs):
    """
    Reads broken diff docs.  This method assumes that the first doc was already
    determined to be broken.
    """
    revision_doc = next(revision_docs)
    yield revision_doc

    while revision_docs.peek(None) is not None and \
          revision_docs.peek()['diff']['last_id'] != revision_doc['id']:

          revision_doc = next(revision_docs)
          yield revision_doc