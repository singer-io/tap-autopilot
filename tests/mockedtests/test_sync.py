"""Mocked integration tests for the full sync pipeline.

These tests mock SESSION.send at the network boundary so that the complete
stack — gen_request → request → SESSION.send — is exercised with simulated
Autopilot API responses.  Singer output (write_record / write_schema /
write_state) is mocked to prevent stdout pollution and to enable assertions.
"""

import io
import json
import unittest
from unittest import mock

import requests
import singer

import tap_autopilot as tap


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _http_resp(json_data, status_code=200):
    resp = mock.MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = mock.MagicMock()
    return resp


def _make_stream(tap_stream_id, selected=True):
    from singer import metadata as md
    schema = tap.load_schema(tap_stream_id)
    mdata = md.new()
    mdata = md.write(mdata, (), "selected", selected)
    return {
        "stream": tap_stream_id,
        "tap_stream_id": tap_stream_id,
        "schema": schema,
        "metadata": md.to_list(mdata),
    }


# ---------------------------------------------------------------------------
# sync_contacts
# ---------------------------------------------------------------------------

class TestSyncContactsIntegration(unittest.TestCase):
    """Full mocked-HTTP integration tests for sync_contacts()."""

    def setUp(self):
        tap.CONFIG["api_key"] = "test-api-key"
        tap.CONFIG["user_agent"] = None
        tap.CONFIG["start_date"] = "2021-01-01T00:00:00Z"

    @mock.patch("tap_autopilot.singer.write_state")
    @mock.patch("tap_autopilot.singer.write_record")
    @mock.patch("tap_autopilot.singer.write_schema")
    @mock.patch("tap_autopilot.SESSION")
    def test_all_sync_branches_in_one_pass(
        self, mock_session, mock_schema, mock_record, mock_state
    ):
        """Single API response exercises every branch in sync_contacts().

        Row coverage:
          c1 (2023-01-01): updated_at present, after start, newer than max  → write + update max
          c2 (2020-12-31): updated_at present, before start                → skip write
          c3 (no ts)     : no updated_at                                   → write (not updated_at is True)
          c4 (2021-01-01): updated_at == start, equal to original max       → write, no max update
        After c1 sets max=2023, c4 cannot advance the max (2021 < 2023).
        """
        mock_session.send.return_value = _http_resp({
            "contacts": [
                {"contact_id": "c1", "updated_at": 1672531200000},  # 2023-01-01
                {"contact_id": "c2", "updated_at": 1609372800000},  # 2020-12-31
                {"contact_id": "c3"},
                {"contact_id": "c4", "updated_at": 1609459200000},  # 2021-01-01 = start
            ],
            "total_contacts": 4,
        })
        stream = _make_stream("contacts")
        final_state = tap.sync_contacts({}, stream)

        # Schema written once with correct key
        mock_schema.assert_called_once_with("contacts", stream["schema"], ["contact_id"])

        # c1, c3, c4 written; c2 (before start) skipped
        written_ids = {c[0][1]["contact_id"] for c in mock_record.call_args_list}
        self.assertEqual(written_ids, {"c1", "c3", "c4"})

        # Bookmark advanced to c1 max (2023-01-01)
        bookmark = singer.get_bookmark(final_state, "contacts", "updated_at")
        self.assertIn("2023", bookmark)

    @mock.patch("tap_autopilot.singer.write_state")
    @mock.patch("tap_autopilot.singer.write_record")
    @mock.patch("tap_autopilot.singer.write_schema")
    @mock.patch("tap_autopilot.SESSION")
    def test_paginated_contacts_all_written(
        self, mock_session, mock_schema, mock_record, mock_state
    ):
        """Paginated API response — all contacts across pages are written."""
        mock_session.send.side_effect = [
            _http_resp({
                "contacts": [{"contact_id": "c1", "updated_at": 1640995200000}],
                "bookmark": "cursor_p2",
                "total_contacts": 2,
            }),
            _http_resp({
                "contacts": [{"contact_id": "c2", "updated_at": 1641081600000}],
                "total_contacts": 2,
            }),
        ]
        stream = _make_stream("contacts")
        tap.sync_contacts({}, stream)
        self.assertEqual(mock_record.call_count, 2)
        self.assertEqual(mock_session.send.call_count, 2)

    @mock.patch("tap_autopilot.singer.write_state")
    @mock.patch("tap_autopilot.singer.write_record")
    @mock.patch("tap_autopilot.singer.write_schema")
    @mock.patch("tap_autopilot.SESSION")
    def test_boolean_props_transformed_before_write(
        self, mock_session, mock_schema, mock_record, mock_state
    ):
        """transform_contact() is applied before singer.write_record."""
        mock_session.send.return_value = _http_resp({
            "contacts": [{
                "contact_id": "c1",
                "updated_at": 1640995200000,
                "anywhere_page_visits": {"https://example.com": True},
            }],
            "total_contacts": 1,
        })
        stream = _make_stream("contacts")
        tap.sync_contacts({}, stream)
        written = mock_record.call_args[0][1]
        self.assertIsInstance(written["anywhere_page_visits"], list)

    @mock.patch("tap_autopilot.singer.write_state")
    @mock.patch("tap_autopilot.singer.write_record")
    @mock.patch("tap_autopilot.singer.write_schema")
    @mock.patch("tap_autopilot.SESSION")
    def test_existing_bookmark_used_as_start(
        self, mock_session, mock_schema, mock_record, mock_state
    ):
        """sync_contacts() resumes from an existing state bookmark."""
        state = singer.write_bookmark({}, "contacts", "updated_at", "2022-06-01T00:00:00Z")
        mock_session.send.return_value = _http_resp({
            "contacts": [
                {"contact_id": "after", "updated_at": 1672531200000},  # 2023-01-01
                {"contact_id": "before", "updated_at": 1640995200000},  # 2022-01-01 < bookmark
            ],
            "total_contacts": 2,
        })
        stream = _make_stream("contacts")
        tap.sync_contacts(state, stream)
        written_ids = {c[0][1]["contact_id"] for c in mock_record.call_args_list}
        self.assertIn("after", written_ids)
        self.assertNotIn("before", written_ids)

    @mock.patch("tap_autopilot.singer.write_state")
    @mock.patch("tap_autopilot.singer.write_record")
    @mock.patch("tap_autopilot.singer.write_schema")
    @mock.patch("tap_autopilot.SESSION")
    def test_empty_contacts_response_writes_state(
        self, mock_session, mock_schema, mock_record, mock_state
    ):
        """sync_contacts() writes state even when API returns no contacts."""
        mock_session.send.return_value = _http_resp({"contacts": [], "total_contacts": 0})
        stream = _make_stream("contacts")
        tap.sync_contacts({}, stream)
        mock_record.assert_not_called()
        mock_state.assert_called()


# ---------------------------------------------------------------------------
# sync_lists
# ---------------------------------------------------------------------------

class TestSyncListsIntegration(unittest.TestCase):
    def setUp(self):
        tap.CONFIG["api_key"] = "test-api-key"
        tap.CONFIG["user_agent"] = None

    @mock.patch("tap_autopilot.singer.write_state")
    @mock.patch("tap_autopilot.singer.write_record")
    @mock.patch("tap_autopilot.singer.write_schema")
    @mock.patch("tap_autopilot.SESSION")
    def test_full_lists_sync(self, mock_session, mock_schema, mock_record, mock_state):
        """All lists from the API are written as Singer records."""
        mock_session.send.return_value = _http_resp({
            "lists": [
                {"list_id": "l1", "title": "Newsletter"},
                {"list_id": "l2", "title": "VIPs"},
            ],
        })
        stream = _make_stream("lists")
        tap.sync_lists({}, stream)
        mock_schema.assert_called_once_with("lists", stream["schema"], ["list_id"])
        self.assertEqual(mock_record.call_count, 2)
        records = [c[0][1] for c in mock_record.call_args_list]
        self.assertEqual(records[0]["list_id"], "l1")
        self.assertEqual(records[1]["list_id"], "l2")

    @mock.patch("tap_autopilot.singer.write_state")
    @mock.patch("tap_autopilot.singer.write_record")
    @mock.patch("tap_autopilot.singer.write_schema")
    @mock.patch("tap_autopilot.SESSION")
    def test_empty_lists_response(self, mock_session, mock_schema, mock_record, mock_state):
        """sync_lists() handles an empty lists array gracefully."""
        mock_session.send.return_value = _http_resp({"lists": []})
        stream = _make_stream("lists")
        tap.sync_lists({}, stream)
        mock_record.assert_not_called()


# ---------------------------------------------------------------------------
# sync_smart_segments
# ---------------------------------------------------------------------------

class TestSyncSmartSegmentsIntegration(unittest.TestCase):
    def setUp(self):
        tap.CONFIG["api_key"] = "test-api-key"
        tap.CONFIG["user_agent"] = None

    @mock.patch("tap_autopilot.singer.write_state")
    @mock.patch("tap_autopilot.singer.write_record")
    @mock.patch("tap_autopilot.singer.write_schema")
    @mock.patch("tap_autopilot.SESSION")
    def test_full_smart_segments_sync(self, mock_session, mock_schema, mock_record, mock_state):
        """All smart segments from the API are written as Singer records."""
        mock_session.send.return_value = _http_resp({
            "segments": [
                {"segment_id": "seg_1", "title": "Ladies"},
                {"segment_id": "seg_2", "title": "Gentlemen"},
            ],
        })
        stream = _make_stream("smart_segments")
        tap.sync_smart_segments({}, stream)
        mock_schema.assert_called_once_with("smart_segments", stream["schema"], ["segment_id"])
        self.assertEqual(mock_record.call_count, 2)

    @mock.patch("tap_autopilot.singer.write_state")
    @mock.patch("tap_autopilot.singer.write_record")
    @mock.patch("tap_autopilot.singer.write_schema")
    @mock.patch("tap_autopilot.SESSION")
    def test_empty_segments_response(self, mock_session, mock_schema, mock_record, mock_state):
        mock_session.send.return_value = _http_resp({"segments": []})
        stream = _make_stream("smart_segments")
        tap.sync_smart_segments({}, stream)
        mock_record.assert_not_called()


# ---------------------------------------------------------------------------
# sync_smart_segment_contacts
# ---------------------------------------------------------------------------

class TestSyncSmartSegmentContactsIntegration(unittest.TestCase):
    def setUp(self):
        tap.CONFIG["api_key"] = "test-api-key"
        tap.CONFIG["user_agent"] = None

    @mock.patch("tap_autopilot.singer.write_state")
    @mock.patch("tap_autopilot.singer.write_record")
    @mock.patch("tap_autopilot.singer.write_schema")
    @mock.patch("tap_autopilot.SESSION")
    def test_contacts_fetched_per_segment_and_written(
        self, mock_session, mock_schema, mock_record, mock_state
    ):
        """Contacts for each segment are fetched separately and written with segment_id."""
        def session_side_effect(req, **kwargs):
            url = req.url
            if "smart_segments/seg_1/contacts" in url:
                return _http_resp({"contacts": [{"contact_id": "c1"}, {"contact_id": "c2"}]})
            if "smart_segments/seg_2/contacts" in url:
                return _http_resp({"contacts": [{"contact_id": "c3"}]})
            return _http_resp({"segments": [{"segment_id": "seg_1"}, {"segment_id": "seg_2"}]})

        mock_session.send.side_effect = session_side_effect
        stream = _make_stream("smart_segments_contacts")
        tap.sync_smart_segment_contacts({}, stream)

        mock_schema.assert_called_once_with(
            "smart_segments_contacts", stream["schema"], ["segment_id", "contact_id"]
        )
        self.assertEqual(mock_record.call_count, 3)
        records = [c[0][1] for c in mock_record.call_args_list]
        self.assertIn({"segment_id": "seg_1", "contact_id": "c1"}, records)
        self.assertIn({"segment_id": "seg_1", "contact_id": "c2"}, records)
        self.assertIn({"segment_id": "seg_2", "contact_id": "c3"}, records)

    @mock.patch("tap_autopilot.singer.write_state")
    @mock.patch("tap_autopilot.singer.write_record")
    @mock.patch("tap_autopilot.singer.write_schema")
    @mock.patch("tap_autopilot.SESSION")
    def test_no_segments_means_no_contact_records(
        self, mock_session, mock_schema, mock_record, mock_state
    ):
        """When no segments exist no contact records are written."""
        mock_session.send.return_value = _http_resp({"segments": []})
        stream = _make_stream("smart_segments_contacts")
        tap.sync_smart_segment_contacts({}, stream)
        mock_record.assert_not_called()


# ---------------------------------------------------------------------------
# do_sync
# ---------------------------------------------------------------------------

class TestDoSyncIntegration(unittest.TestCase):
    def setUp(self):
        tap.CONFIG["api_key"] = "test-api-key"
        tap.CONFIG["user_agent"] = None
        tap.CONFIG["start_date"] = "2021-01-01T00:00:00Z"

    def _catalog(self, stream_ids, selected=True):
        return {"streams": [_make_stream(sid, selected) for sid in stream_ids]}

    @mock.patch("tap_autopilot.singer.write_state")
    @mock.patch("tap_autopilot.singer.write_record")
    @mock.patch("tap_autopilot.singer.write_schema")
    @mock.patch("tap_autopilot.SESSION")
    def test_selected_streams_trigger_api_calls(
        self, mock_session, mock_schema, mock_record, mock_state
    ):
        """do_sync() makes at least one API call per selected stream."""
        def side_effect(req, **kwargs):
            if "/contacts" in req.url:
                return _http_resp({"contacts": [], "total_contacts": 0})
            return _http_resp({"lists": []})

        mock_session.send.side_effect = side_effect
        tap.do_sync({}, self._catalog(["contacts", "lists"]))
        self.assertGreaterEqual(mock_session.send.call_count, 2)

    @mock.patch("tap_autopilot.singer.write_state")
    @mock.patch("tap_autopilot.SESSION")
    def test_unselected_streams_no_api_calls(self, mock_session, mock_state):
        """do_sync() makes no API calls when no streams are selected."""
        tap.do_sync({}, self._catalog(["contacts", "lists"], selected=False))
        mock_session.send.assert_not_called()

    @mock.patch("tap_autopilot.singer.write_state")
    @mock.patch("tap_autopilot.singer.write_record")
    @mock.patch("tap_autopilot.singer.write_schema")
    @mock.patch("tap_autopilot.SESSION")
    def test_resumes_from_currently_syncing_state(
        self, mock_session, mock_schema, mock_record, mock_state
    ):
        """do_sync() skips streams before currently_syncing and only calls the API for remaining streams."""
        state = singer.set_currently_syncing({}, "lists")
        mock_session.send.return_value = _http_resp({"lists": []})
        tap.do_sync(state, self._catalog(["contacts", "lists"]))
        # Every SESSION.send call must be for the lists URL (contacts skipped)
        for call in mock_session.send.call_args_list:
            self.assertIn("/lists", call[0][0].url)


# ---------------------------------------------------------------------------
# discover_schemas / do_discover
# ---------------------------------------------------------------------------

class TestDiscoverIntegration(unittest.TestCase):
    def test_discover_schemas_returns_all_four_streams(self):
        result = tap.discover_schemas()
        stream_ids = [s["tap_stream_id"] for s in result["streams"]]
        self.assertCountEqual(
            stream_ids,
            ["contacts", "lists", "smart_segments", "smart_segments_contacts"],
        )

    def test_discover_schemas_each_stream_has_schema_and_metadata(self):
        for stream in tap.discover_schemas()["streams"]:
            self.assertIn("schema", stream)
            self.assertIn("properties", stream["schema"])
            self.assertIn("metadata", stream)
            self.assertTrue(len(stream["metadata"]) > 0)

    def test_do_discover_writes_valid_json_catalog_to_stdout(self):
        buf = io.StringIO()
        with mock.patch("tap_autopilot.sys.stdout", buf):
            tap.do_discover()
        buf.seek(0)
        catalog = json.load(buf)
        self.assertIn("streams", catalog)
        self.assertGreater(len(catalog["streams"]), 0)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

class TestMainIntegration(unittest.TestCase):
    def setUp(self):
        tap.CONFIG.update({"api_key": None, "start_date": None, "user_agent": None})

    def _args(self, *, discover=False, properties=None, state=None):
        args = mock.MagicMock()
        args.config = {"api_key": "test-key", "start_date": "2021-01-01T00:00:00Z"}
        args.state = state
        args.discover = discover
        args.properties = properties
        return args

    @mock.patch("tap_autopilot.utils.parse_args")
    @mock.patch("tap_autopilot.do_discover")
    def test_discover_mode_calls_do_discover(self, mock_discover, mock_parse_args):
        """main() calls do_discover() when --discover flag is present."""
        mock_parse_args.return_value = self._args(discover=True)
        tap.main()
        mock_discover.assert_called_once()

    @mock.patch("tap_autopilot.utils.parse_args")
    @mock.patch("tap_autopilot.SESSION")
    def test_properties_mode_runs_do_sync(self, mock_session, mock_parse_args):
        """main() runs do_sync() and makes API calls when --properties (catalog) is provided."""
        stream = _make_stream("lists")
        catalog = {"streams": [stream]}
        mock_parse_args.return_value = self._args(properties=catalog)
        mock_session.send.return_value = _http_resp({"lists": []})

        with mock.patch("tap_autopilot.singer.write_record"),              mock.patch("tap_autopilot.singer.write_schema"),              mock.patch("tap_autopilot.singer.write_state"):
            tap.main()

        mock_session.send.assert_called()

    @mock.patch("tap_autopilot.utils.parse_args")
    def test_state_loaded_into_STATE(self, mock_parse_args):
        """main() merges existing state dict into STATE before syncing."""
        incoming_state = {"bookmarks": {"contacts": {"updated_at": "2022-01-01T00:00:00Z"}}}
        mock_parse_args.return_value = self._args(state=incoming_state)
        # No properties → LOGGER.info path, no crash
        tap.main()

    @mock.patch("tap_autopilot.utils.parse_args")
    def test_no_streams_logs_and_returns(self, mock_parse_args):
        """main() logs and exits cleanly when neither --discover nor --properties is set."""
        mock_parse_args.return_value = self._args()
        tap.main()  # Must complete without error


if __name__ == "__main__":
    unittest.main()
