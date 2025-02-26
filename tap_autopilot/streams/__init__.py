from tap_autopilot.streams.contacts import Contacts
from tap_autopilot.streams.lists import Lists
from tap_autopilot.streams.smart_segments import Smart_segments
from tap_autopilot.streams.smart_segments_contacts import Smart_segments_contacts

STREAMS = {
    'contacts': Contacts,
    'lists': Lists,
    'smart_segments': Smart_segments,
    'smart_segments_contacts': Smart_segments_contacts,
}