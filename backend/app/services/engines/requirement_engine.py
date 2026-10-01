from typing import Any, Dict, List
from backend.app.schemas.requirement import RequirementPayload
from backend.app.schemas.bom import BOMLineSpec
from backend.app.services.rules.wtvision_graphics import evaluate_wtvision_graphics_rules
from backend.app.models.solution import Solution
from pydantic import ValidationError

class RequirementEngineError(Exception):
    pass

def parse_and_evaluate_requirements(solution: Solution, raw_data: Dict[str, Any]) -> List[BOMLineSpec]:
    """
    Parses raw requirement JSON into a structured RequirementPayload,
    executing all validation and dependency cascades.
    Then dispatches the payload to the appropriate business rule engine
    based on the Solution.
    """
    try:
        payload = RequirementPayload(**raw_data)
    except ValidationError as e:
        raise RequirementEngineError(f"Requirement validation failed: {str(e)}")

    if solution.name == "WTVision Graphics":
        return evaluate_wtvision_graphics_rules(payload)
    else:
        raise RequirementEngineError(f"No business rules engine implemented for solution: {solution.name}")
