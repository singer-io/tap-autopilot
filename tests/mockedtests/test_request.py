"""Mocked integration tests for the HTTP request and pagination layer.

These tests mock SESSION.send at the network boundary and run the full
request() / gen_request() stack, simulating real Autopilot API calls.
"""

import unittest
from unittest import mock

import requests

import tap_autopilot as tap


def _http_resp(json_data, status_code=200):
    """Build a mock requests.Response with the given JSON payload."""
    resp = mock.MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = mock.MagicMock()
    return resp


class TestRequestIntegration(unittest.TestCase):
    """Integration tests for request() — HTTP headers, bookmark, error handling."""

    def setUp(self):
        tap.CONFIG["api_key"] = "test-api-key"
        tap.CONFIG["user_agent"] = None

    @mock.patch("tap_autopilot.SESSION")
    def test_api_key_header_sent(self, mock_session):
        """API key is placed in the autopilotapikey header on every request."""
        mock_session.send.return_value = _http_resp({"contacts": []})
        tap.request("https://api2.autopilothq.com/v1/contacts")
        req = mock_session.send.call_args[0][0]
        self.assertEqual(req.headers.get("autopilotapikey"), "test-api-key")

    @mock.patch("tap_autopilot.SESSION")
    def test_user_agent_header_set_when_configured(self, mock_session):
        """user-agent header is included only when CONFIG[user_agent] is set."""
        tap.CONFIG["user_agent"] = "tap-autopilot/1.0"
        mock_session.send.return_value = _http_resp({"contacts": []})
        tap.request("https://api2.autopilothq.com/v1/contacts")
        req = mock_session.send.call_args[0][0]
        self.assertEqual(req.headers.get("user-agent"), "tap-autopilot/1.0")

    @mock.patch("tap_autopilot.SESSION")
    def test_user_agent_header_absent_when_none(self, mock_session):
        """user-agent header is absent when CONFIG[user_agent] is None."""
        tap.CONFIG["user_agent"] = None
        mock_session.send.return_value = _http_resp({"contacts": []})
        tap.request("https://api2.autopilothq.com/v1/contacts")
        req = mock_session.send.call_args[0][0]
        self.assertNotIn("user-agent", req.headers)

    @mock.patch("tap_autopilot.SESSION")
    def test_bookmark_appended_to_url(self, mock_session):
        """Bookmark token is appended to the URL path for paginated requests."""
        mock_session.send.return_value = _http_resp({"contacts": []})
        tap.request(
            "https://api2.autopilothq.com/v1/contacts",
            params={"bookmark": "cursor_ABC123"},
        )
        req = mock_session.send.call_args[0][0]
        self.assertTrue(req.url.endswith("/cursor_ABC123"))

    @mock.patch("tap_autopilot.SESSION")
    def test_no_bookmark_url_unchanged(self, mock_session):
        """URL is unchanged when params dict has no bookmark key."""
        mock_session.send.return_value = _http_resp({"contacts": []})
        tap.request("https://api2.autopilothq.com/v1/contacts", params={})
        req = mock_session.send.call_args[0][0]
        self.assertEqual(req.url, "https://api2.autopilothq.com/v1/contacts")

    @mock.patch("tap_autopilot.SESSION")
    def test_no_params_url_unchanged(self, mock_session):
        """URL is unchanged when params is None."""
        mock_session.send.return_value = _http_resp({"contacts": []})
        tap.request("https://api2.autopilothq.com/v1/contacts", params=None)
        req = mock_session.send.call_args[0][0]
        self.assertEqual(req.url, "https://api2.autopilothq.com/v1/contacts")

    @mock.patch("tap_autopilot.SESSION")
    def test_http_response_returned(self, mock_session):
        """request() returns the raw response object."""
        expected = _http_resp({"contacts": []})
        mock_session.send.return_value = expected
        result = tap.request("https://api2.autopilothq.com/v1/contacts")
        self.assertIs(result, expected)

    @mock.patch("tap_autopilot.SESSION")
    def test_4xx_client_error_raises_immediately(self, mock_session):
        """4xx errors (except 408) trigger giveup and raise without retry."""
        resp = _http_resp({}, status_code=404)
        http_err = requests.exceptions.HTTPError(response=resp)
        resp.raise_for_status.side_effect = http_err
        mock_session.send.return_value = resp

        with self.assertRaises(requests.exceptions.HTTPError):
            tap.request("https://api2.autopilothq.com/v1/contacts")

        # giveup=client_error fires on the first attempt — no retries
        self.assertEqual(mock_session.send.call_count, 1)


class TestGenRequestIntegration(unittest.TestCase):
    """Integration tests for gen_request() — pagination and endpoint routing."""

    def setUp(self):
        tap.CONFIG["api_key"] = "test-api-key"
        tap.CONFIG["user_agent"] = None

    @mock.patch("tap_autopilot.SESSION")
    def test_contacts_single_page_yields_all_rows(self, mock_session):
        """All contacts from a single-page API response are yielded."""
        mock_session.send.return_value = _http_resp({
            "contacts": [
                {"contact_id": "c1", "Email": "a@example.com"},
                {"contact_id": "c2", "Email": "b@example.com"},
            ],
            "total_contacts": 2,
        })
        results = list(tap.gen_request({}, "https://api2.autopilothq.com/v1/contacts"))
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["contact_id"], "c1")
        self.assertEqual(results[1]["contact_id"], "c2")

    @mock.patch("tap_autopilot.SESSION")
    def test_contacts_paginated_transparently(self, mock_session):
        """gen_request() follows bookmark pagination and yields rows from all pages."""
        mock_session.send.side_effect = [
            _http_resp({
                "contacts": [{"contact_id": "c1"}],
                "bookmark": "cursor_p2",
                "total_contacts": 2,
            }),
            _http_resp({
                "contacts": [{"contact_id": "c2"}],
                "total_contacts": 2,
            }),
        ]
        results = list(tap.gen_request({}, "https://api2.autopilothq.com/v1/contacts"))
        self.assertEqual(len(results), 2)
        self.assertEqual(mock_session.send.call_count, 2)
        # Second request URL should include the bookmark
        second_req = mock_session.send.call_args_list[1][0][0]
        self.assertIn("cursor_p2", second_req.url)

    @mock.patch("tap_autopilot.SESSION")
    def test_contacts_default_params_none(self, mock_session):
        """gen_request() works when params=None (defaults to empty dict internally)."""
        mock_session.send.return_value = _http_resp({
            "contacts": [{"contact_id": "c1"}],
            "total_contacts": 1,
        })
        results = list(tap.gen_request({}, "https://api2.autopilothq.com/v1/contacts", params=None))
        self.assertEqual(len(results), 1)

    @mock.patch("tap_autopilot.SESSION")
    def test_contacts_empty_response_yields_nothing(self, mock_session):
        """gen_request() yields nothing for an empty contacts array."""
        mock_session.send.return_value = _http_resp({"contacts": [], "total_contacts": 0})
        self.assertEqual(
            list(tap.gen_request({}, "https://api2.autopilothq.com/v1/contacts")),
            [],
        )

    @mock.patch("tap_autopilot.SESSION")
    def test_lists_endpoint_yields_list_rows(self, mock_session):
        """gen_request() uses the lists key for the /lists endpoint."""
        mock_session.send.return_value = _http_resp({
            "lists": [{"list_id": "l1", "title": "Alpha"}, {"list_id": "l2", "title": "Beta"}],
        })
        results = list(tap.gen_request({}, "https://api2.autopilothq.com/v1/lists"))
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["list_id"], "l1")

    @mock.patch("tap_autopilot.SESSION")
    def test_smart_segments_endpoint_yields_segment_rows(self, mock_session):
        """gen_request() uses the segments key for the /smart_segments endpoint."""
        mock_session.send.return_value = _http_resp({
            "segments": [{"segment_id": "seg_1", "title": "VIPs"}],
        })
        results = list(tap.gen_request({}, "https://api2.autopilothq.com/v1/smart_segments"))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["segment_id"], "seg_1")

    @mock.patch("tap_autopilot.SESSION")
    def test_smart_segment_contacts_endpoint_yields_contacts(self, mock_session):
        """gen_request() uses the contacts key for smart_segment contact sub-URLs."""
        mock_session.send.return_value = _http_resp({
            "contacts": [{"contact_id": "c1"}, {"contact_id": "c2"}],
        })
        url = "https://api2.autopilothq.com/v1/smart_segments/seg_1/contacts"
        results = list(tap.gen_request({}, url))
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["contact_id"], "c1")


if __name__ == "__main__":
    unittest.main()
