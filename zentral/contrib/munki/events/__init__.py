import logging
import uuid
from dateutil import parser
from zentral.core.events.base import BaseEvent, EventMetadata, EventRequest, register_event_type

logger = logging.getLogger('zentral.contrib.munki.events')


ALL_EVENTS_SEARCH_DICT = {"tag": "munki"}


class MunkiEnrollmentEvent(BaseEvent):
    event_type = "munki_enrollment"
    tags = ["munki"]


register_event_type(MunkiEnrollmentEvent)


class MunkiRequestEvent(BaseEvent):
    event_type = "munki_request"
    tags = ["munki", "heartbeat"]
    heartbeat_timeout = 2 * 3600


register_event_type(MunkiRequestEvent)


class MunkiEvent(BaseEvent):
    event_type = "munki_event"
    tags = ["munki"]
    payload_aggregations = [
        ("munki_version", {"type": "terms", "bucket_number": 10, "label": "Munki versions"}),
        ("run_type", {"type": "terms", "bucket_number": 10, "label": "Run types"}),
        ("type", {"type": "terms", "bucket_number": 10, "label": "Types"}),
        ("name", {"type": "table", "bucket_number": 50, "label": "Bundles",
                  "columns": [("name", "Name"),
                              ("version", "Version str.")]}),
    ]

    def get_linked_objects_keys(self):
        keys = {}
        event_type = self.payload.get("type")
        if event_type in ("install", "removal"):
            name = self.payload.get("name")
            if name:
                keys["munki_pkginfo_name"] = [(name,)]
                version = self.payload.get("version")
                if version:
                    keys["munki_pkginfo"] = [(name, version)]
        return keys


register_event_type(MunkiEvent)


def post_munki_request_event(msn, user_agent, ip, **kwargs):
    metadata = EventMetadata(
        machine_serial_number=msn,
        request=EventRequest(user_agent, ip),
        incident_updates=kwargs.pop("incident_updates", [])
    )
    event = MunkiRequestEvent(metadata, kwargs)
    event.post()


def post_munki_events(msn, user_agent, ip, data):
    for report in data:
        events = report.pop('events')
        event_uuid = uuid.uuid4()
        for event_index, (created_at, payload) in enumerate(events):
            metadata = EventMetadata(
                uuid=event_uuid,
                index=event_index,
                request=EventRequest(user_agent, ip),
                created_at=parser.parse(created_at),
                incident_updates=payload.pop("incident_updates", []),
            )
            payload.update(report)
            event = MunkiEvent(metadata, payload)
            event.post()


def post_munki_enrollment_event(msn, user_agent, ip, data):
    MunkiEnrollmentEvent.post_machine_request_payloads(msn, user_agent, ip, [data])
