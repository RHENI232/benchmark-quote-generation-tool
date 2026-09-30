"""stable catalog identity

Revision ID: 77cd83799512
Revises: c9830790673a
Create Date: 2026-09-30 15:29:10.158045

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import uuid

# revision identifiers, used by Alembic.
revision: str = '77cd83799512'
down_revision: Union[str, Sequence[str], None] = 'c9830790673a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Hardcoded permanent mapping for shipped baseline items
APPROVED_MAPPING = [
    {"lookup_key": "cat_wtv_000001", "part_number": "MT1010", "description": "Ingest – base unit, 1 per box", "kind": "RULE_DRIVEN"},
    {"lookup_key": "cat_wtv_000002", "part_number": "MT1011", "description": "Each extra channel beyond the first in its box", "kind": "RULE_DRIVEN"},
    {"lookup_key": "cat_wtv_000003", "part_number": "MT1020", "description": "Trimmer, one per channel", "kind": "RULE_DRIVEN"},
    {"lookup_key": "cat_wtv_000004", "part_number": "BDLKDVQD2", "description": "Ingest Capture Card (4-channel)", "kind": "RULE_DRIVEN"},
    {"lookup_key": "cat_wtv_000005", "part_number": "INGSVR101", "description": "Ingest Server hardware, one per box", "kind": "RULE_DRIVEN"},
    {"lookup_key": "cat_wtv_000006", "part_number": "MM1000", "description": "wTVision Media Manager, includes 1 Media Agent", "kind": "RULE_DRIVEN"},
    {"lookup_key": "cat_wtv_000007", "part_number": "MA1001", "description": "Extra Locations/Media Agents, one per studio", "kind": "RULE_DRIVEN"},
    {"lookup_key": "cat_wtv_000008", "part_number": "MAMSVR101", "description": "MAM Server hardware", "kind": "RULE_DRIVEN"},
    {"lookup_key": "cat_wtv_000009", "part_number": "MP0001", "description": "wTVision Media Server, Single Channel FHD", "kind": "RULE_DRIVEN"},
    {"lookup_key": "cat_wtv_000010", "part_number": "MP0012", "description": "First Input Manager", "kind": "RULE_DRIVEN"},
    {"lookup_key": "cat_wtv_000011", "part_number": "SC1000", "description": "Studio CG — central control app", "kind": "RULE_DRIVEN"},
    {"lookup_key": "cat_wtv_000012", "part_number": "STDCG101", "description": "Studio CG Control PC hardware", "kind": "RULE_DRIVEN"},
    {"lookup_key": "cat_wtv_000013", "part_number": "PL1001", "description": "R³ Engine Plugin for Studio CG", "kind": "RULE_DRIVEN"},
    {"lookup_key": "cat_wtv_000014", "part_number": "PL1004", "description": "Media Server Controller Plugin", "kind": "RULE_DRIVEN"},
    {"lookup_key": "cat_wtv_000015", "part_number": "R30001", "description": "Graphics Engine (Base)", "kind": "RULE_DRIVEN"},
    {"lookup_key": "cat_wtv_000016", "part_number": "R3ENG101", "description": "Graphics Engine Companion Hardware", "kind": "RULE_DRIVEN"},
    {"lookup_key": "cat_wtv_000017", "part_number": "BDLKDVQD2", "description": "Graphics IO card", "kind": "RULE_DRIVEN"},
    {"lookup_key": "cat_wtv_000018", "part_number": "R30010", "description": "Dual Channel", "kind": "RULE_DRIVEN"},
    {"lookup_key": "cat_wtv_000019", "part_number": "R30020", "description": "Extra Live Input", "kind": "RULE_DRIVEN"},
    {"lookup_key": "cat_wtv_000020", "part_number": "wG4000", "description": "LED Video Wall (4 outputs)", "kind": "RULE_DRIVEN"},
    {"lookup_key": "cat_wtv_000021", "part_number": "wG8000", "description": "LED Video Wall (8 outputs)", "kind": "RULE_DRIVEN"},
    {"lookup_key": "cat_wtv_000022", "part_number": "vWALLENG101", "description": "LED Video Wall Engine", "kind": "RULE_DRIVEN"},
    {"lookup_key": "cat_wtv_000023", "part_number": "UE0002", "description": "VR-AR Unreal Engine Base", "kind": "RULE_DRIVEN"},
    {"lookup_key": "cat_wtv_000024", "part_number": "ARENG101", "description": "VR-AR Engine Hardware", "kind": "RULE_DRIVEN"},
    {"lookup_key": "cat_wtv_000025", "part_number": "wV3000", "description": "VR-AR Unreal Bundle", "kind": "RULE_DRIVEN"},
    {"lookup_key": "cat_wtv_000026", "part_number": "IMMVRENG101", "description": "VR-AR Unreal Engine Companion", "kind": "RULE_DRIVEN"},
    {"lookup_key": "cat_wtv_000027", "part_number": "BDLKHCPRO8K12GG2", "description": "Capture Card — spec TBC", "kind": "RULE_DRIVEN"},
    {"lookup_key": "cat_wtv_000028", "part_number": "DE1001", "description": "R³ Designer", "kind": "RULE_DRIVEN"},
    {"lookup_key": "cat_wtv_000029", "part_number": "R3DES101", "description": "R³ Designer Workstation hardware", "kind": "RULE_DRIVEN"},
    {"lookup_key": "cat_wtv_000030", "part_number": "MG1000", "description": "NRCS Integration Base", "kind": "RULE_DRIVEN"},
    {"lookup_key": "cat_wtv_000031", "part_number": "NP1010", "description": "NRCS Integration (10 Journalists)", "kind": "RULE_DRIVEN"},
    {"lookup_key": "cat_wtv_000032", "part_number": "NP1025", "description": "NRCS Integration (25 Journalists)", "kind": "RULE_DRIVEN"},
    {"lookup_key": "cat_wtv_000033", "part_number": "NP1050", "description": "NRCS Integration (50 Journalists)", "kind": "RULE_DRIVEN"},
    {"lookup_key": "cat_wtv_000034", "part_number": "MG1001", "description": "MOS Redundancy", "kind": "RULE_DRIVEN"},
    {"lookup_key": "cat_wtv_000035", "part_number": "PW1000", "description": "NRCS Graphics Preview", "kind": "RULE_DRIVEN"},
    {"lookup_key": "cat_wtv_000036", "part_number": "NLE105", "description": "NLE Plugin (5 Seats)", "kind": "RULE_DRIVEN"},
    {"lookup_key": "cat_wtv_000037", "part_number": "NLE110", "description": "NLE Plugin (10 Seats)", "kind": "RULE_DRIVEN"},
    {"lookup_key": "cat_wtv_000038", "part_number": "NLE115", "description": "NLE Plugin (15 Seats)", "kind": "RULE_DRIVEN"},
    {"lookup_key": "cat_wtv_000039", "part_number": "PS1050", "description": "Professional Services (Variant A)", "kind": "REFERENCE"},
    {"lookup_key": "cat_wtv_000040", "part_number": "PS1050", "description": "Professional Services (Variant B)", "kind": "REFERENCE"},
    {"lookup_key": "cat_wtv_000041", "part_number": "R31050", "description": "Render Engine Option A", "kind": "REFERENCE"},
    {"lookup_key": "cat_wtv_000042", "part_number": "R31050", "description": "Render Engine Option B", "kind": "REFERENCE"},
    {"lookup_key": "cat_wtv_000043", "part_number": "NLE110", "description": "NLE Plugin (15 Seats variant)", "kind": "REFERENCE"},
    {"lookup_key": "cat_wtv_000044", "part_number": None, "description": "PCR-ENGINE concept (Part Number TBC)", "kind": "REFERENCE"},
]

def upgrade() -> None:
    # 1. Add lookup_key as nullable
    op.add_column('catalog_items', sa.Column('lookup_key', sa.String(), nullable=True))

    bind = op.get_bind()

    # 2. Match exact Solution
    sols = bind.execute(sa.text("SELECT id FROM solutions WHERE name = 'WTVision Graphics'")).fetchall()
    if len(sols) == 0:
        raise Exception("Migration aborted: WTVision Graphics solution not found.")
    if len(sols) > 1:
        raise Exception("Migration aborted: Multiple WTVision Graphics solutions found.")
    
    sol_id = sols[0][0]

    # 3. Match EXACTLY ONE existing row for each baseline item
    for item in APPROVED_MAPPING:
        lk = item["lookup_key"]
        pn = item["part_number"]
        desc = item["description"]
        kind = item["kind"]

        if pn is None:
            query = sa.text("""
                SELECT id FROM catalog_items 
                WHERE solution_id = :sid AND kind = :kind AND part_number IS NULL AND description = :desc
            """)
            res = bind.execute(query, {"sid": sol_id, "kind": kind, "desc": desc}).fetchall()
        else:
            query = sa.text("""
                SELECT id FROM catalog_items 
                WHERE solution_id = :sid AND kind = :kind AND part_number = :pn AND description = :desc
            """)
            res = bind.execute(query, {"sid": sol_id, "kind": kind, "pn": pn, "desc": desc}).fetchall()
        
        if len(res) == 0:
            raise Exception(f"Migration aborted: 0 matches for {pn} - {desc}")
        if len(res) > 1:
            raise Exception(f"Migration aborted: >1 match for {pn} - {desc}")

        item_id = res[0][0]

        # Assign permanent lookup_key, leaving catalog_items.id completely intact
        bind.execute(
            sa.text("UPDATE catalog_items SET lookup_key = :lk WHERE id = :id"),
            {"lk": lk, "id": item_id}
        )

    # 4. Assign cat_usr_<uuid4 hex> to all remaining rows
    unmapped_records = bind.execute(sa.text("SELECT id FROM catalog_items WHERE lookup_key IS NULL")).fetchall()
    for row in unmapped_records:
        bind.execute(
            sa.text("UPDATE catalog_items SET lookup_key = :lk WHERE id = :id"),
            {"lk": f"cat_usr_{uuid.uuid4().hex}", "id": row[0]}
        )
        
    # 5. Verify no NULLs remain
    null_count = bind.execute(sa.text("SELECT COUNT(*) FROM catalog_items WHERE lookup_key IS NULL")).scalar()
    if null_count > 0:
        raise Exception("Migration aborted: Not all rows were assigned a lookup_key.")
        
    # 6. Verify Uniqueness
    total_count = bind.execute(sa.text("SELECT COUNT(*) FROM catalog_items")).scalar()
    distinct_count = bind.execute(sa.text("SELECT COUNT(DISTINCT lookup_key) FROM catalog_items")).scalar()
    if total_count != distinct_count:
        raise Exception("Migration aborted: lookup_key values are not unique.")

    # 7. Apply Constraints
    op.alter_column('catalog_items', 'lookup_key', existing_type=sa.String(), nullable=False)
    # Prefer one clear uniqueness mechanism consistent with SQLAlchemy `unique=True, index=True`
    op.create_index(op.f('ix_catalog_items_lookup_key'), 'catalog_items', ['lookup_key'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_catalog_items_lookup_key'), table_name='catalog_items')
    op.drop_column('catalog_items', 'lookup_key')
