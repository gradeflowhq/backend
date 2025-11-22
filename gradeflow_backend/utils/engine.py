from typing import cast

from pydantic import BaseModel

# Strongly-typed recursive JSON types
JSONScalar = str | int | float | bool | None
JSONDict = dict[str, "JSONValue"]
JSONList = list["JSONValue"]
JSONValue = JSONScalar | JSONDict | JSONList

ENGINE_FIELDS: set[str] = {
    "question_types",
    "constraints",
}


def remove_engine_fields(data: JSONValue) -> JSONValue:
    if isinstance(data, dict):
        result: JSONDict = {}
        for k, v in data.items():
            if k not in ENGINE_FIELDS:
                result[k] = remove_engine_fields(v)
        return result
    elif isinstance(data, list):
        return [remove_engine_fields(item) for item in data]
    else:
        # JSONScalar
        return data


def model_dump_minimal(obj: BaseModel) -> JSONValue:
    # Pydantic returns a dict[str, Any]; cast to our JSONDict for typing
    data = cast(JSONDict, obj.model_dump())
    cleaned = remove_engine_fields(data)
    return cleaned
