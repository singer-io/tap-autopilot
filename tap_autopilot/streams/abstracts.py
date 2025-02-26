from abc import ABC, abstractmethod
from typing import Any, Dict, Tuple, List

from singer import (
    Transformer,
    get_bookmark,
    get_logger,
    metrics,
    write_bookmark,
    write_record,
    write_schema,
)
from singer.utils import  strptime_with_tz

LOGGER = get_logger()


class BaseStream(ABC):
    """
    A Base Class providing structure and boilerplate for generic streams
    and required attributes for any kind of stream
    ~~~
    Provides:
     - Basic Attributes (stream_name,replication_method,key_properties)
     - Helper methods for catalog generation
     - `sync` and `get_records` method for performing sync
    """

    url_endpoint = ""
    path = ""
    page_size = 100
    next_page_key = "bookmark"
    headers = {"Accept": "application/json"}
    children = []
    parent = ""
    data_key = ""

    def __init__(self, client=None, schema=None, metadata=None) -> None:
        self.client = client
        self.schema = schema
        self.metadata = metadata
        self.child_to_sync = []
        self.params = {}

    @property
    @abstractmethod
    def tap_stream_id(self) -> str:
        """Unique identifier for the stream.

        This is allowed to be different from the name of the stream, in
        order to allow for sources that have duplicate stream names.
        """

    @property
    @abstractmethod
    def replication_method(self) -> str:
        """Defines the sync mode of a stream."""

    @property
    @abstractmethod
    def replication_keys(self) -> str:
        """Defines the replication key for incremental sync mode of a
        stream."""

    @property
    @abstractmethod
    def forced_replication_method(self) -> str:
        """Defines the sync mode of a stream."""

    @property
    @abstractmethod
    def key_properties(self) -> Tuple[str, str]:
        """List of key properties for stream."""

    @property
    def selected_by_default(self) -> bool:
        """Indicates if a node in the schema should be replicated, if a user
        has not expressed any opinion on whether or not to replicate it."""
        return False

    @abstractmethod
    def sync(
        self,
        state: Dict,
        transformer: Transformer,
        parent_obj: Dict = None,
    ) -> Dict:
        """
        Performs a replication sync for the stream.
        ~~~
        Args:
         - state (dict): represents the state file for the tap.
         - transformer (object): A Object of the singer.transformer class.
         - parent_obj (dict): The parent object for the stream.

        Returns:
         - bool: The return value. True for success, False otherwise.

        Docs:
         - https://github.com/singer-io/getting-started/blob/master/docs/SYNC_MODE.md
        """

    def get_records(self) -> List:
        """Interacts with api client interaction and pagination."""
        bookmark = ""
        while bookmark is not None:
            response = self.client.get(
                self.url_endpoint, self.params, self.headers, self.path
            )
            raw_records = response.get(self.data_key, [])

            bookmark = response.get(self.next_page_key)
            if bookmark:
                url_endpoint = url_endpoint + "/" + bookmark
            yield from raw_records

    def write_schema(self):
        """
        Write a schema message.
        """
        try:
            write_schema(self.tap_stream_id, self.schema, self.key_properties)
        except OSError as err:
            LOGGER.error(
                "OS Error while writing schema for: {}".format(self.tap_stream_id)
            )
            raise err

    def get_url_endpoint(self, parent_obj: Dict = None) -> str:
        """
        Get the URL endpoint for the stream
        """
        return f"{self.client.base_url}/{self.path}"


class IncrementalStream(BaseStream):
    """Base Class for Incremental Stream."""

    replication_method = "INCREMENTAL"
    forced_replication_method = "INCREMENTAL"
    config_start_key = "start_date"

    def get_bookmark(self, state: dict, key: Any = None) -> int:
        """A wrapper for singer.get_bookmark to deal with compatibility for
        bookmark values or start values."""
        return get_bookmark(
            state,
            self.tap_stream_id,
            key or self.replication_keys[0],
            self.client.config.get(self.config_start_key, False),
        )

    def write_bookmark(self, state: dict, key: Any = None, value: Any = None) -> Dict:
        """A wrapper for singer.get_bookmark to deal with compatibility for
        bookmark values or start values."""
        return write_bookmark(
            state, self.tap_stream_id, key or self.replication_keys[0], value
        )

    def sync(
        self,
        state: Dict,
        transformer: Transformer,
        parent_obj: Dict = None,
    ) -> Dict:
        """Implementation for `type: Incremental` stream."""
        current_max_bookmark_date = bookmark_date = strptime_with_tz(
            self.get_bookmark(state)
        )
        self.url_endpoint = self.get_url_endpoint()

        with metrics.record_counter(self.tap_stream_id) as counter:
            for record in self.get_records():
                transformed_record = transformer.transform(
                    record, self.schema, self.metadata
                )
                record_updated_at = strptime_with_tz(
                    transformed_record[self.replication_keys[0]]
                )
                if record_updated_at >= bookmark_date:
                    write_record(self.tap_stream_id, transformed_record)
                    current_max_bookmark_date = max(
                        current_max_bookmark_date, record_updated_at
                    )
                    counter.increment()

                    for child in self.child_to_sync:
                        child.sync(
                            state=state, transformer=transformer, parent_obj=record
                        )

            state = self.write_bookmark(state, value=current_max_bookmark_date)
            return counter.value


class FullTableStream(BaseStream):
    """Base Class for Incremental Stream."""

    replication_method = "FULL_TABLE"
    forced_replication_method = "FULL_TABLE"
    valid_replication_keys = None
    replication_keys = None

    def sync(
        self,
        state: Dict,
        transformer: Transformer,
        parent_obj: Dict = None,
    ) -> Dict:
        """Abstract implementation for `type: Fulltable` stream."""
        self.url_endpoint = self.get_url_endpoint()
        with metrics.record_counter(self.tap_stream_id) as counter:
            for record in self.get_records():
                transformed_record = transformer.transform(
                    record, self.schema, self.metadata
                )
                write_record(self.tap_stream_id, transformed_record)
                counter.increment()

                for child in self.child_to_sync:
                    child.sync(state=state, transformer=transformer, parent_obj=record)

            return counter.value
