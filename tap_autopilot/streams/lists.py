from tap_autopilot.streams.abstracts import FullTableStream


class Lists(FullTableStream):
    tap_stream_id = "lists"
    key_properties = ["list_id"]
    data_key = "lists"
    path = "lists"
