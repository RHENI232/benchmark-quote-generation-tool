import pytest
from pydantic import ValidationError
from backend.app.schemas.requirement import RequirementPayload, StudioRequirement
from backend.app.services.rules.wtvision_graphics import evaluate_wtvision_graphics_rules
from backend.app.services.engines.requirement_engine import parse_and_evaluate_requirements, RequirementEngineError
from backend.app.models.solution import Solution

def test_requirement_payload_cascades():
    # Test valid cascade (mos_redundancy forces news_production)
    payload = RequirementPayload(
        number_of_studios=1,
        studios=[
            StudioRequirement(studio_index=0, studio_type="Real Set", number_of_engines=0)
        ],
        mos_redundancy=True, # Should force news_production=True
        production_playout=True, # Should force mam=True
        sdi_production_ingest=False,
        ingest_channels=5 # Should be cleared to 0
    )
    
    assert payload.news_production is True
    assert payload.mam is True
    assert payload.ingest_channels == 0

def test_studio_requirement_cascades():
    # Test studio cascades
    studio = StudioRequirement(
        studio_index=0,
        studio_type="Real Set",
        number_of_cameras=3, # Should be cleared because not Unreal
        led_video_wall=False,
        led_outputs=4, # Should be cleared because led_video_wall is False
        number_of_engines=0,
        dual_channel=True, # Should be cleared because engines = 0
        extra_live_input=True # Should be cleared because engines = 0
    )
    
    assert studio.number_of_cameras is None
    assert studio.led_outputs is None
    assert studio.dual_channel is False
    assert studio.extra_live_input is False

def test_requirement_payload_validation_errors():
    with pytest.raises(ValidationError):
        # Mismatched number of studios vs array length
        RequirementPayload(
            number_of_studios=2,
            studios=[
                StudioRequirement(studio_index=0, studio_type="Real Set")
            ]
        )
        
    with pytest.raises(ValidationError):
        # Mismatched studio_index
        RequirementPayload(
            number_of_studios=1,
            studios=[
                StudioRequirement(studio_index=1, studio_type="Real Set")
            ]
        )

def test_wtvision_graphics_rules():
    payload = RequirementPayload(
        number_of_studios=1,
        studios=[
            StudioRequirement(
                studio_index=0,
                studio_type="VR-AR (Unreal)",
                number_of_cameras=2,
                number_of_control_clients=2
            )
        ],
        sdi_production_ingest=True,
        ingest_channels=5,
        number_of_designers=1
    )
    
    bom = evaluate_wtvision_graphics_rules(payload)
    
    # Ingest calculations: 5 channels -> 2 boxes (MT1010), 3 extra (MT1011), 5 trimmers (MT1020), 2 cards, 2 servers
    ingest_items = {item.lookup_key: item.quantity for item in bom if item.section == "Ingest"}
    assert ingest_items["cat_wtv_000001"] == 2 # MT1010
    assert ingest_items["cat_wtv_000002"] == 3 # MT1011
    assert ingest_items["cat_wtv_000003"] == 5 # MT1020
    assert ingest_items["cat_wtv_000004"] == 2 # BDLKDVQD2
    assert ingest_items["cat_wtv_000005"] == 2 # INGSVR101

    # VR-AR Unreal calculations
    graphics_items = {item.lookup_key: item.quantity for item in bom if item.section == "Graphics Engine"}
    assert graphics_items["cat_wtv_000025"] == 1 # wV3000
    assert graphics_items["cat_wtv_000026"] == 4 # IMMVRENG101 (2 cameras * 2)
    assert graphics_items["cat_wtv_000027"] == 2 # BDLKHCPRO8K12GG2 (2 cameras)

    # Control clients
    playout_items = {item.lookup_key: item.quantity for item in bom if item.section == "Playout Controller"}
    assert playout_items["cat_wtv_000011"] == 2 # SC1000
    
def test_requirement_engine_dispatcher():
    solution = Solution(name="WTVision Graphics")
    raw_data = {
        "number_of_studios": 1,
        "studios": [
            {
                "studio_index": 0,
                "studio_type": "Real Set"
            }
        ],
        "production_playout": True
    }
    
    bom = parse_and_evaluate_requirements(solution, raw_data)
    
    # Production playout adds MP0001 (000009) and MP0012 (000010)
    # Plus PL1004 (000014) in Playout Controller
    # And it cascades to MAM, which adds MM1000 (000006), MA1001 (000007), MAMSVR101 (000008)
    
    keys = [item.lookup_key for item in bom]
    assert "cat_wtv_000009" in keys
    assert "cat_wtv_000014" in keys
    assert "cat_wtv_000006" in keys
    
    # Invalid solution tests
    bad_solution = Solution(name="Unknown Solution")
    with pytest.raises(RequirementEngineError):
        parse_and_evaluate_requirements(bad_solution, raw_data)
