from typing import List, Optional, Literal
from pydantic import BaseModel, Field, model_validator, field_validator

class StudioRequirement(BaseModel):
    studio_index: int = Field(..., ge=0)
    studio_type: Literal["Real Set", "VR-AR (R3 Engine)", "VR-AR (Unreal)"]
    number_of_cameras: Optional[int] = Field(None, ge=1, le=3)
    led_video_wall: bool = False
    led_outputs: Optional[Literal[4, 8]] = None
    number_of_engines: int = Field(0, ge=0)
    dual_channel: bool = False
    extra_live_input: bool = False
    number_of_control_clients: int = Field(0, ge=0)

    @model_validator(mode="after")
    def cascade_and_validate(self) -> "StudioRequirement":
        # led_video_wall=false -> clear led_outputs
        if not self.led_video_wall:
            self.led_outputs = None

        # number_of_engines=0 -> force dual_channel=false, extra_live_input=false
        if self.number_of_engines == 0:
            self.dual_channel = False
            self.extra_live_input = False

        # number_of_cameras validation: only applicable for Unreal? The spec says:
        # "number_of_cameras (1-3, only for Unreal)". Let's enforce that.
        if self.studio_type != "VR-AR (Unreal)":
            self.number_of_cameras = None
            
        return self


class RequirementPayload(BaseModel):
    number_of_studios: int = Field(..., ge=1, le=12)
    number_of_designers: int = Field(0, ge=0)
    news_production: bool = False
    journalists: Optional[Literal[10, 25, 50]] = None
    mos_redundancy: bool = False
    nle_plugin: bool = False
    nle_seats: Optional[Literal[5, 10, 15]] = None
    nrcs_graphics_preview: bool = False
    sdi_production_ingest: bool = False
    ingest_channels: int = Field(0, ge=0)
    production_playout: bool = False
    mam: bool = False
    three_years_support: bool = False
    studios: List[StudioRequirement] = Field(default_factory=list)

    @model_validator(mode="after")
    def cascade_and_validate(self) -> "RequirementPayload":
        # mos_redundancy=true -> force news_production=true
        if self.mos_redundancy:
            self.news_production = True
            
        # nrcs_graphics_preview=true -> force news_production=true
        if self.nrcs_graphics_preview:
            self.news_production = True
            
        # production_playout=true -> force mam=true
        if self.production_playout:
            self.mam = True

        # news_production=false -> clear journalists to None
        if not self.news_production:
            self.journalists = None

        # nle_plugin=false -> clear nle_seats to None
        if not self.nle_plugin:
            self.nle_seats = None

        # sdi_production_ingest=false -> set ingest_channels=0
        if not self.sdi_production_ingest:
            self.ingest_channels = 0
            
        # Ensure studios length matches number_of_studios
        if len(self.studios) != self.number_of_studios:
            raise ValueError(f"Expected {self.number_of_studios} studios, but got {len(self.studios)}")
            
        # Enforce strict 0-based studio_index alignment
        for idx, studio in enumerate(self.studios):
            if studio.studio_index != idx:
                raise ValueError(f"Studio at array index {idx} has mismatched studio_index {studio.studio_index}")

        return self
