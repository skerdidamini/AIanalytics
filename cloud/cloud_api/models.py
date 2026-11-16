from typing import Annotated, Literal, Union
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator, field_validator

Identifier = Annotated[str, StringConstraints(min_length=1, max_length=128, strip_whitespace=False)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)


class TrackDetails(StrictModel):
    track_id: Identifier


class ZoneDetails(TrackDetails):
    zone_id: Identifier
    direction: Literal['entered', 'exited']


class DwellDetails(TrackDetails):
    zone_id: Identifier
    duration_seconds: float = Field(ge=0, le=31536000)
    completion: Literal['zone_exit', 'track_lost', 'stream_ended']
    censored: bool

    @model_validator(mode='after')
    def completion_matches(self):
        if self.censored != (self.completion != 'zone_exit'):
            raise ValueError('Censoring must match completion')
        return self


class OccupancyDetails(StrictModel):
    visible_persons: int = Field(ge=0, le=1000000)
    zones: dict[Identifier, Annotated[int, Field(ge=0, le=1000000)]] = Field(max_length=100)
    scope: Literal['camera_visible_only']

    @model_validator(mode='after')
    def valid_zones(self):
        if any(count > self.visible_persons for count in self.zones.values()):
            raise ValueError('Zone counts exceed camera visible count')
        return self


class Event(StrictModel):
    event_id: str
    timestamp: float = Field(ge=0)
    organization_id: Identifier
    location_id: Identifier
    node_id: Identifier
    camera_id: Identifier

    @model_validator(mode='after')
    def uuid_id(self):
        if str(UUID(self.event_id)) != self.event_id:
            raise ValueError('Canonical UUID event_id required')
        return self


class CrossingEvent(Event):
    type: Literal['person_entered', 'person_exited']
    details: TrackDetails


class ZoneEvent(Event):
    type: Literal['zone_crossed']
    details: ZoneDetails


class DwellEvent(Event):
    type: Literal['dwell_time_completed']
    details: DwellDetails


class OccupancyEvent(Event):
    type: Literal['occupancy_snapshot']
    details: OccupancyDetails


AnyEvent = Annotated[Union[CrossingEvent, ZoneEvent, DwellEvent, OccupancyEvent], Field(discriminator='type')]


class Batch(StrictModel):
    schema_version: Literal[1]
    events: list[AnyEvent] = Field(min_length=1, max_length=100)

    @field_validator('schema_version', mode='before')
    @classmethod
    def integer_version(cls, value):
        if type(value) is not int:
            raise ValueError('Integer schema version required')
        return value
