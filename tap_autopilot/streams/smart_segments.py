from tap_autopilot.streams.abstracts import FullTableStream


class Smart_segments(FullTableStream):
    tap_stream_id = "smart_segments"
    key_properties = ["segment_id"]
    data_key = "segments"
    path = "smart_segments"
    children = ["smart_segments_contacts"]
