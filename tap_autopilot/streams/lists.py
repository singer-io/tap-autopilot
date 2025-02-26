from singer import get_logger
from tap_autopilot.streams.abstracts import FullTableStream

LOGGER = get_logger()

class Lists(FullTableStream):
    tap_stream_id = 'lists'
    key_properties = ['list_id']
    data_key = 'lists'
    path = 'lists'
