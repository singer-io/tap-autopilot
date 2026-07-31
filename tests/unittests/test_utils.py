"""Unit tests for pure utility functions in tap_autopilot.

These tests exercise every branch of every non-HTTP function to achieve
100% branch coverage on tap_autopilot/__init__.py.
"""

import os
import unittest
from unittest import mock

import requests
import singer

import tap_autopilot as tap


# ---------------------------------------------------------------------------
# SourceUnavailableException
# ---------------------------------------------------------------------------

class TestSourceUnavailableException(unittest.TestCase):
    def test_is_exception_subclass(self):
        self.assertTrue(issubclass(tap.SourceUnavailableException, Exception))

    def test_can_be_raised_and_caught(self):
        with self.assertRaises(tap.SourceUnavailableException):
            raise tap.SourceUnavailableException("unavailable")

    def test_stores_message(self):
        self.assertEqual(str(tap.SourceUnavailableException("oops")), "oops")


# ---------------------------------------------------------------------------
# get_abs_path / load_schema
# ---------------------------------------------------------------------------

class TestGetAbsPath(unittest.TestCase):
    def test_returns_absolute_path(self):
        self.assertTrue(os.path.isabs(tap.get_abs_path("schemas/contacts.json")))

    def test_points_to_existing_file(self):
        self.assertTrue(os.path.exists(tap.get_abs_path("schemas/contacts.json")))


class TestLoadSchema(unittest.TestCase):
    def test_contacts_schema_has_properties(self):
        self.assertIn("properties", tap.load_schema("contacts"))

    def test_lists_schema_has_properties(self):
        self.assertIn("properties", tap.load_schema("lists"))

    def test_smart_segments_schema_has_properties(self):
        self.assertIn("properties", tap.load_schema("smart_segments"))

    def test_smart_segments_contacts_schema_has_properties(self):
        self.assertIn("properties", tap.load_schema("smart_segments_contacts"))


# ---------------------------------------------------------------------------
# parse_source_from_url — 4 distinct branches
# ---------------------------------------------------------------------------

class TestParseSourceFromUrl(unittest.TestCase):
    # Branch A: match, group(1)=="contacts", "segment" NOT in URL
    def test_contacts_url_returns_contacts(self):
        self.assertEqual(
            tap.parse_source_from_url("https://api2.autopilothq.com/v1/contacts"),
            "contacts",
        )

    # Branch B: match, group(1)=="contacts", "segment" IN URL
    def test_smart_segment_contacts_url(self):
        self.assertEqual(
            tap.parse_source_from_url(
                "https://api2.autopilothq.com/v1/smart_segments/seg_abc/contacts"
            ),
            "smart_segments_contacts",
        )

    # Branch C: match, group(1) != "contacts"
    def test_lists_url_returns_lists(self):
        self.assertEqual(
            tap.parse_source_from_url("https://api2.autopilothq.com/v1/lists"),
            "lists",
        )

    def test_smart_segments_url_returns_smart_segments(self):
        self.assertEqual(
            tap.parse_source_from_url("https://api2.autopilothq.com/v1/smart_segments"),
            "smart_segments",
        )

    def test_custom_fields_url_returns_custom_fields(self):
        self.assertEqual(
            tap.parse_source_from_url(
                "https://api2.autopilothq.com/v1/contacts/custom_fields"
            ),
            "custom_fields",
        )

    # Branch D: no match → ValueError
    def test_invalid_url_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            tap.parse_source_from_url("https://example.com/unknown")
        self.assertIn("Can't determine stream", str(ctx.exception))


# ---------------------------------------------------------------------------
# parse_key_from_source — 3 branches
# ---------------------------------------------------------------------------

class TestParseKeyFromSource(unittest.TestCase):
    # Branch A: 'contact' in source
    def test_contacts_returns_contacts(self):
        self.assertEqual(tap.parse_key_from_source("contacts"), "contacts")

    def test_smart_segments_contacts_returns_contacts(self):
        self.assertEqual(tap.parse_key_from_source("smart_segments_contacts"), "contacts")

    # Branch B: 'smart_segments' in source (but not 'contact')
    def test_smart_segments_returns_segments(self):
        self.assertEqual(tap.parse_key_from_source("smart_segments"), "segments")

    # Branch C: neither — return source unchanged
    def test_lists_returns_lists(self):
        self.assertEqual(tap.parse_key_from_source("lists"), "lists")

    def test_custom_source_returns_itself(self):
        self.assertEqual(tap.parse_key_from_source("custom_fields"), "custom_fields")


# ---------------------------------------------------------------------------
# get_url
# ---------------------------------------------------------------------------

class TestGetUrl(unittest.TestCase):
    def test_contacts_endpoint(self):
        self.assertEqual(tap.get_url("contacts"), "https://api2.autopilothq.com/v1/contacts")

    def test_lists_endpoint(self):
        self.assertEqual(tap.get_url("lists"), "https://api2.autopilothq.com/v1/lists")

    def test_smart_segments_endpoint(self):
        self.assertEqual(
            tap.get_url("smart_segments"),
            "https://api2.autopilothq.com/v1/smart_segments",
        )

    def test_custom_fields_endpoint(self):
        self.assertEqual(
            tap.get_url("custom_fields"),
            "https://api2.autopilothq.com/v1/contacts/custom_fields",
        )

    def test_smart_segments_contacts_with_segment_id(self):
        self.assertEqual(
            tap.get_url("smart_segments_contacts", segment_id="seg_abc"),
            "https://api2.autopilothq.com/v1/smart_segments/seg_abc/contacts",
        )

    # Branch: endpoint not in ENDPOINTS → ValueError
    def test_invalid_endpoint_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            tap.get_url("nonexistent")
        self.assertIn("Invalid endpoint", str(ctx.exception))


# ---------------------------------------------------------------------------
# client_error — all branches of the compound boolean
# ---------------------------------------------------------------------------

class TestClientError(unittest.TestCase):
    def _exc(self, status_code=None):
        exc = requests.exceptions.RequestException()
        if status_code is not None:
            exc.response = mock.MagicMock()
            exc.response.status_code = status_code
        else:
            exc.response = None
        return exc

    def test_no_response_returns_false(self):
        self.assertFalse(tap.client_error(self._exc(None)))

    def test_408_returns_false(self):
        self.assertFalse(tap.client_error(self._exc(408)))

    def test_400_returns_true(self):
        self.assertTrue(tap.client_error(self._exc(400)))

    def test_404_returns_true(self):
        self.assertTrue(tap.client_error(self._exc(404)))

    def test_499_returns_true(self):
        self.assertTrue(tap.client_error(self._exc(499)))

    def test_500_returns_false(self):
        self.assertFalse(tap.client_error(self._exc(500)))

    def test_301_returns_false(self):
        self.assertFalse(tap.client_error(self._exc(301)))


# ---------------------------------------------------------------------------
# transform_contact — every boolean/timestamp prop branch
# ---------------------------------------------------------------------------

class TestTransformContact(unittest.TestCase):
    def test_anywhere_page_visits_converted_to_list(self):
        contact = {"anywhere_page_visits": {"https://a.com": True, "https://b.com": False}}
        result = tap.transform_contact(contact)
        self.assertIsInstance(result["anywhere_page_visits"], list)
        urls = {item["url"] for item in result["anywhere_page_visits"]}
        self.assertEqual(urls, {"https://a.com", "https://b.com"})
        for item in result["anywhere_page_visits"]:
            self.assertIn("url", item)
            self.assertIn("value", item)

    def test_anywhere_form_submits_converted(self):
        contact = {"anywhere_form_submits": {"https://form.com": True}}
        result = tap.transform_contact(contact)
        self.assertIsInstance(result["anywhere_form_submits"], list)

    def test_anywhere_utm_converted(self):
        contact = {"anywhere_utm": {"utm_src": True}}
        result = tap.transform_contact(contact)
        self.assertIsInstance(result["anywhere_utm"], list)

    def test_absent_boolean_prop_not_added(self):
        contact = {"email": "x@x.com"}
        tap.transform_contact(contact)
        self.assertNotIn("anywhere_page_visits", contact)

    def test_empty_boolean_prop_becomes_empty_list(self):
        contact = {"anywhere_page_visits": {}}
        self.assertEqual(tap.transform_contact(contact)["anywhere_page_visits"], [])

    def test_mail_received_converted_to_list(self):
        contact = {"mail_received": {"id1": 1609459200000}}
        result = tap.transform_contact(contact)
        self.assertIsInstance(result["mail_received"], list)
        row = result["mail_received"][0]
        self.assertEqual(row["id"], "id1")
        self.assertIn("timestamp", row)

    def test_all_seven_timestamp_props_converted(self):
        ts_props = [
            "mail_received", "mail_opened", "mail_clicked",
            "mail_bounced", "mail_complained", "mail_unsubscribed", "mail_hardbounced",
        ]
        contact = {p: {"id_x": 1609459200000} for p in ts_props}
        result = tap.transform_contact(contact)
        for p in ts_props:
            self.assertIsInstance(result[p], list, msg=f"{p} not converted")

    def test_absent_timestamp_prop_not_added(self):
        contact = {"email": "x@x.com"}
        tap.transform_contact(contact)
        self.assertNotIn("mail_received", contact)

    def test_empty_timestamp_prop_becomes_empty_list(self):
        contact = {"mail_opened": {}}
        self.assertEqual(tap.transform_contact(contact)["mail_opened"], [])

    def test_unrelated_props_unchanged(self):
        contact = {"contact_id": "abc", "Email": "x@x.com"}
        result = tap.transform_contact(contact)
        self.assertEqual(result["contact_id"], "abc")
        self.assertEqual(result["Email"], "x@x.com")


# ---------------------------------------------------------------------------
# get_start — bookmark absent vs present
# ---------------------------------------------------------------------------

class TestGetStart(unittest.TestCase):
    def setUp(self):
        tap.CONFIG["start_date"] = "2021-01-01T00:00:00Z"

    def test_returns_start_date_when_no_bookmark(self):
        self.assertEqual(tap.get_start({}, "contacts", "updated_at"), "2021-01-01T00:00:00Z")

    def test_returns_bookmark_when_present(self):
        state = singer.write_bookmark({}, "contacts", "updated_at", "2022-06-01T00:00:00Z")
        self.assertEqual(tap.get_start(state, "contacts", "updated_at"), "2022-06-01T00:00:00Z")


# ---------------------------------------------------------------------------
# get_streams_to_sync — all 3 branches
# ---------------------------------------------------------------------------

class TestGetStreamsToSync(unittest.TestCase):
    def _streams(self):
        return [
            {"tap_stream_id": "contacts"},
            {"tap_stream_id": "lists"},
            {"tap_stream_id": "smart_segments"},
        ]

    def test_no_current_stream_returns_all(self):
        result = tap.get_streams_to_sync(self._streams(), {})
        self.assertEqual(result, self._streams())

    def test_current_stream_drops_preceding(self):
        state = singer.set_currently_syncing({}, "lists")
        result = tap.get_streams_to_sync(self._streams(), state)
        self.assertEqual([s["tap_stream_id"] for s in result], ["lists", "smart_segments"])

    def test_unknown_current_stream_raises(self):
        state = singer.set_currently_syncing({}, "nonexistent")
        with self.assertRaises(Exception) as ctx:
            tap.get_streams_to_sync(self._streams(), state)
        self.assertIn("Unknown stream", str(ctx.exception))


# ---------------------------------------------------------------------------
# get_selected_streams — selected True vs False
# ---------------------------------------------------------------------------

class TestGetSelectedStreams(unittest.TestCase):
    def _stream(self, tap_stream_id, selected):
        from singer import metadata as md
        mdata = md.new()
        mdata = md.write(mdata, (), "selected", selected)
        return {"tap_stream_id": tap_stream_id, "metadata": md.to_list(mdata)}

    def test_selected_stream_included(self):
        result = tap.get_selected_streams([
            self._stream("contacts", True),
            self._stream("lists", False),
        ])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["tap_stream_id"], "contacts")

    def test_unselected_stream_not_included(self):
        self.assertEqual(tap.get_selected_streams([self._stream("contacts", False)]), [])

    def test_all_selected_returns_all(self):
        self.assertEqual(
            len(tap.get_selected_streams([
                self._stream("contacts", True),
                self._stream("lists", True),
            ])),
            2,
        )

    def test_empty_list_returns_empty(self):
        self.assertEqual(tap.get_selected_streams([]), [])


# ---------------------------------------------------------------------------
# sync — routing to each sync function
# ---------------------------------------------------------------------------

class TestSyncRouting(unittest.TestCase):
    def _stream(self, tap_stream_id):
        from singer import metadata as md
        schema = tap.load_schema(tap_stream_id)
        mdata = md.new()
        mdata = md.write(mdata, (), "selected", True)
        return {
            "stream": tap_stream_id,
            "tap_stream_id": tap_stream_id,
            "schema": schema,
            "metadata": md.to_list(mdata),
        }

    @mock.patch("tap_autopilot.sync_contacts", return_value={"routed": "contacts"})
    def test_routes_contacts(self, mock_fn):
        result = tap.sync({}, self._stream("contacts"))
        mock_fn.assert_called_once()
        self.assertEqual(result, {"routed": "contacts"})

    @mock.patch("tap_autopilot.sync_lists", return_value={"routed": "lists"})
    def test_routes_lists(self, mock_fn):
        result = tap.sync({}, self._stream("lists"))
        mock_fn.assert_called_once()
        self.assertEqual(result, {"routed": "lists"})

    @mock.patch("tap_autopilot.sync_smart_segments", return_value={"routed": "segs"})
    def test_routes_smart_segments(self, mock_fn):
        result = tap.sync({}, self._stream("smart_segments"))
        mock_fn.assert_called_once()
        self.assertEqual(result, {"routed": "segs"})

    @mock.patch("tap_autopilot.sync_smart_segment_contacts", return_value={"routed": "seg_c"})
    def test_routes_smart_segment_contacts(self, mock_fn):
        result = tap.sync({}, self._stream("smart_segments_contacts"))
        mock_fn.assert_called_once()
        self.assertEqual(result, {"routed": "seg_c"})


if __name__ == "__main__":
    unittest.main()
