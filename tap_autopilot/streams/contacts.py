from typing import Dict
from singer import get_logger
from tap_autopilot.streams.abstracts import IncrementalStream

LOGGER = get_logger()


class Contacts(IncrementalStream):
    tap_stream_id = "contacts"
    key_properties = ["contact_id"]
    replication_keys = ["updated_at"]
    data_key = "contacts"
    path = "contacts"

    def get_url_endpoint(self, parent_obj: Dict = None) -> str:
        """Get the URL endpoint for the stream."""
        return f"{self.client.base_url}/{self.path}/bookmark"
