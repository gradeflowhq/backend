from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RuleTypeOption(BaseModel):
    type: str
    label: str


class CompatibleRulesResponse(BaseModel):
    rules: list[RuleTypeOption]


class RuleSchemaResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    json_schema: dict[str, Any] = Field(..., alias="schema")
    initial_value: dict[str, Any] = Field(default_factory=dict)
