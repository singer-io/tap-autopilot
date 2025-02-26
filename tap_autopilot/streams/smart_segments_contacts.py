from typing import Dict
from singer import Transformer, get_logger, metrics, write_record
from tap_autopilot.streams.abstracts import FullTableStream

LOGGER = get_logger()

class Smart_segments_contacts(FullTableStream):
    tap_stream_id = 'smart_segments_contacts'
    key_properties = ['segment_id', 'contact_id']
    data_key = 'smart_segments_contacts'
    path = 'smart_segments/{}/contacts'
    parent = 'smart_segments'

    def get_url_endpoint(self, parent_obj=None):
        """
        Get the URL endpoint for the stream
        """
        return f"{self.client.base_url}/{self.path.format(parent_obj['segment_id'])}"

    def sync(
        self,
        state: Dict,
        transformer: Transformer,
        parent_obj: Dict = None,
    ) -> Dict:
        """Abstract implementation for `type: Fulltable` stream."""
        self.url_endpoint = self.get_url_endpoint(parent_obj)
        with metrics.record_counter(self.tap_stream_id) as counter:
            for record in self.get_records():
                record = {
                    "segment_id": parent_obj["segment_id"],
                    "contact_id": record["contact_id"]
                }

                write_record(self.tap_stream_id, record)
                counter.increment()

            return counter.value