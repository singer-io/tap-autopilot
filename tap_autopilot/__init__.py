#!/usr/bin/env python3

import os
import time
import re
import json

import backoff
import pendulum
import requests
import dateutil.parser
import singer
import singer.metrics as metrics
from singer import utils

REQUIRED_CONFIG_KEYS = ["api_key", "user_agent"]
PER_PAGE = 100
BASE_URL = "https://api2.autopilothq.com/v1"


LOGGER = singer.get_logger()
SESSION = requests.session()

# class InvalidAuthException(Exception):
#     LOGGER.info("Invalid Auth Exception")

# class SourceUnavailableException(Exception):
#     LOGGER.info("Source Unavailable Exception")

CONFIG = {}
STATE = {}

ENDPOINTS = {
    "contacts":                "/contacts/",
    "lists_contacts":          "/lists/{list_id}/contacts/",
    "lists":                   "/lists/",
    "smart_segments_contacts": "/smart_segments/",
    "smart_segments":          "/smart_segments/{smart_segment_id}/contacts/",
}


def get_abs_path(path):
    '''Returns the absolute path'''
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), path)


def load_schema(entity):
    '''Returns the schema for the specified source'''
    return utils.load_json(get_abs_path("schemas/{}.json".format(entity)))


def client_error(exc):
    '''Indicates whether the given RequestException is a 4xx response'''
    return exc.response is not None and 400 <= exc.response.status_code < 500


def parse_source_from_url(url):
    '''Given an Autopilot URL, extract the source name (e.g. "contacts")'''
    url_regex = re.compile(BASE_URL +  r'.*/(\w+)\/')
    match = url_regex.match(url)
    # LOGGER.info(match.group(1))

    if match:
        return match.group(1)

    raise ValueError("Can't determine stream from URL " + url)


def get_start(key):
    '''Get the start date from CONFIG or STATE

    TODO: THIS NEEDS TESTING
    There is no updated_at field that I've seen on contacts
    This could be useful for lists and smart segments but it
    might result in missing contacts that were added after the last sync.
    '''
    if key not in STATE:
        STATE[key] = CONFIG["start_date"]

    return STATE[key]


def get_bookmark(key):
    '''Retrieve a bookmark from STATE if it exists'''
    if key in STATE:
        return STATE[key]

    return None


def get_url(endpoint):
    '''Get the full url for the endpoint'''
    if endpoint not in ENDPOINTS:
        raise ValueError("Invalid endpoint {}".format(endpoint))

    return BASE_URL + ENDPOINTS[endpoint]


@backoff.on_exception(backoff.expo,
                      (requests.exceptions.RequestException),
                      max_tries=5,
                      giveup=client_error,
                      factor=2)
def request(url, params=None):
    '''Make a request to the given Autopilot URL.
    Handles retrying, status checking. Logs request duration and records
    per second
    '''
    headers = {"autopilotapikey": CONFIG["api_key"]}
    if "user_agent" in CONFIG:
        headers["user-agent"] = CONFIG["user_agent"]

    LOGGER.info("GET %s", url)
    with metrics.http_request_timer(parse_source_from_url(url)) as timer:
        req = requests.Request("GET", url, headers=headers, params=params).prepare()
        resp = SESSION.send(req)
        timer.tags[metrics.Tag.http_status_code] = resp.status_code
        resp.raise_for_status()
        return resp


def gen_request(endpoint, params=None):
    '''Generate a request that will iterate through the results
    and paginate through the responses until the amount of results
    returned is less than 100, the amount returned by the API.
    '''
    params = params or {}

    source = parse_source_from_url(endpoint)

    with metrics.record_counter(source) as counter:
        while True:
            data = request(endpoint, params).json()

            for row in data[source]:
                counter.increment()
                yield row

            if len(data[source]) < PER_PAGE:
                break


def sync_contacts():
    '''Sync contacts from the Autopilot API'''
    LOGGER.info("Starting Contacts Sync")

    schema = load_schema("contacts")
    singer.write_schema("contacts", schema, ["contact_id"])

    bookmark = get_bookmark("contacts")
    params = {bookmark: bookmark}

    for row in gen_request(get_url("contacts"), params):
        singer.write_record("contacts", row)
        utils.update_state(STATE, "contacts", row["contact_id"])

    singer.write_state(STATE)


def sync_lists():
    '''Sync all lists from the Autopilot API'''
    LOGGER.info("Starting Lists Sync")


def sync_list_contacts():
    '''Sync the contacts on a given list from the Autopilot API'''
    LOGGER.info("Starting List's Contacts Sync")


def sync_smart_segments():
    '''Sync all smart segments from the Autopilot API'''
    LOGGER.info("Starting Smart Segments Sync")


def sync_smart_segment_contacts():
    '''Sync the contacts on a given smart segment from the Autopilot API'''
    LOGGER.info("Starting Smart Segment's Contacts Sync")



def do_sync():
    LOGGER.info("Starting sync")
    sync_contacts()
    sync_lists()
    sync_list_contacts()
    sync_smart_segments()
    sync_smart_segment_contacts()
    LOGGER.info("Completed sync")


def main():
    '''Entry point'''
    args = utils.parse_args(REQUIRED_CONFIG_KEYS)
    CONFIG.update(args.config)

    if args.state:
        STATE.update(args.state)

    do_sync()


if __name__ == "__main__":
    main()
