from typing import List, Dict, Tuple
from collections import defaultdict
import math
from backend.app.schemas.requirement import RequirementPayload
from backend.app.schemas.bom import BOMLineSpec

def evaluate_wtvision_graphics_rules(payload: RequirementPayload) -> List[BOMLineSpec]:
    # Use a dictionary to aggregate quantities: (section, lookup_key) -> quantity
    bom_aggregation: Dict[Tuple[str, str], int] = defaultdict(int)

    def add_item(section: str, lookup_key: str, qty: int):
        if qty > 0:
            bom_aggregation[(section, lookup_key)] += qty

    # Section 4.1: Ingest
    if payload.sdi_production_ingest and payload.ingest_channels > 0:
        c = payload.ingest_channels
        boxes = math.ceil(c / 4.0)
        
        add_item("Ingest", "cat_wtv_000001", boxes) # MT1010
        add_item("Ingest", "cat_wtv_000002", c - boxes) # MT1011
        add_item("Ingest", "cat_wtv_000003", c) # MT1020
        add_item("Ingest", "cat_wtv_000004", boxes) # BDLKDVQD2 (Ingest variant)
        add_item("Ingest", "cat_wtv_000005", boxes) # INGSVR101

    # Section 4.2: MAM
    if payload.mam:
        add_item("MAM", "cat_wtv_000006", 1) # MM1000
        add_item("MAM", "cat_wtv_000007", payload.number_of_studios) # MA1001
        add_item("MAM", "cat_wtv_000008", 1) # MAMSVR101

    # Section 4.3: Production Playout
    if payload.production_playout:
        add_item("Production Playout", "cat_wtv_000009", 1) # MP0001
        add_item("Production Playout", "cat_wtv_000010", 1) # MP0012

    # Section 4.4: Playout Controller
    total_control_clients = sum(s.number_of_control_clients for s in payload.studios if hasattr(s, 'number_of_control_clients'))
    if total_control_clients > 0:
        add_item("Playout Controller", "cat_wtv_000011", total_control_clients) # SC1000
        add_item("Playout Controller", "cat_wtv_000012", total_control_clients) # STDCG101
        add_item("Playout Controller", "cat_wtv_000013", total_control_clients) # PL1001
    if payload.production_playout:
        add_item("Playout Controller", "cat_wtv_000014", 1) # PL1004

    # Section 4.5: Graphics Engine
    for studio in payload.studios:
        # 4.5.1 Base rule
        engines = studio.number_of_engines
        if engines >= 1:
            add_item("Graphics Engine", "cat_wtv_000015", engines) # R30001
            add_item("Graphics Engine", "cat_wtv_000016", engines) # R3ENG101
            add_item("Graphics Engine", "cat_wtv_000017", engines) # BDLKDVQD2 (Graphics IO variant)
            if studio.dual_channel:
                add_item("Graphics Engine", "cat_wtv_000018", 1) # R30010
            if studio.extra_live_input:
                add_item("Graphics Engine", "cat_wtv_000019", 1) # R30020

        # 4.5.2 LED Video Wall
        if studio.led_video_wall:
            if studio.led_outputs == 4:
                add_item("Graphics Engine", "cat_wtv_000020", 1) # wG4000
                add_item("Graphics Engine", "cat_wtv_000017", 1) # BDLKDVQD2 (Graphics IO)
            elif studio.led_outputs == 8:
                add_item("Graphics Engine", "cat_wtv_000021", 1) # wG8000
                add_item("Graphics Engine", "cat_wtv_000017", 2) # BDLKDVQD2 (Graphics IO)
            add_item("Graphics Engine", "cat_wtv_000022", 1) # vWALLENG101

        # 4.5.3 VR-AR (R3 Engine)
        if studio.studio_type == "VR-AR (R3 Engine)":
            add_item("Graphics Engine", "cat_wtv_000015", 1) # R30001
            add_item("Graphics Engine", "cat_wtv_000016", 1) # R3ENG101
            add_item("Graphics Engine", "cat_wtv_000017", 1) # BDLKDVQD2 (Graphics IO)
            add_item("Graphics Engine", "cat_wtv_000023", 1) # UE0002
            add_item("Graphics Engine", "cat_wtv_000024", 1) # ARENG101

        # 4.5.4 VR-AR (Unreal)
        if studio.studio_type == "VR-AR (Unreal)":
            cams = studio.number_of_cameras or 1
            add_item("Graphics Engine", "cat_wtv_000025", 1) # wV3000
            add_item("Graphics Engine", "cat_wtv_000026", cams * 2) # IMMVRENG101
            add_item("Graphics Engine", "cat_wtv_000027", cams) # BDLKHCPRO8K12GG2

    # Section 4.6: Designer Tools
    if payload.number_of_designers > 0:
        add_item("Designer Tools", "cat_wtv_000028", payload.number_of_designers) # DE1001
        add_item("Designer Tools", "cat_wtv_000029", payload.number_of_designers) # R3DES101

    # Section 4.7: NRCS Integration
    if payload.news_production:
        add_item("NRCS Integration", "cat_wtv_000030", 1) # MG1000
        if payload.journalists == 10:
            add_item("NRCS Integration", "cat_wtv_000031", 1) # NP1010
        elif payload.journalists == 25:
            add_item("NRCS Integration", "cat_wtv_000032", 1) # NP1025
        elif payload.journalists == 50:
            add_item("NRCS Integration", "cat_wtv_000033", 1) # NP1050

    if payload.mos_redundancy:
        add_item("NRCS Integration", "cat_wtv_000034", 1) # MG1001

    if payload.nrcs_graphics_preview:
        add_item("NRCS Integration", "cat_wtv_000035", 1) # PW1000

    # Section 4.8: NLE Plugin
    if payload.nle_plugin:
        if payload.nle_seats == 5:
            add_item("NLE Plugin", "cat_wtv_000036", 1) # NLE105
        elif payload.nle_seats == 10:
            add_item("NLE Plugin", "cat_wtv_000037", 1) # NLE110
        elif payload.nle_seats == 15:
            add_item("NLE Plugin", "cat_wtv_000038", 1) # NLE115
            
    # Assemble final list
    return [
        BOMLineSpec(section=sec, lookup_key=lk, quantity=qty)
        for (sec, lk), qty in bom_aggregation.items()
    ]
