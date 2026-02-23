from enum import Enum
from uuid import UUID


def to_db_payload(
    payload: object,
    *,
    exclude_none: bool = False,
    uuid_fields: set[str] | None = None,
    enum_fields: set[str] | None = None,
) -> dict:
    if hasattr(payload, 'model_dump'):
        data = payload.model_dump(exclude_none=exclude_none)
    elif isinstance(payload, dict):
        data = dict(payload)
        if exclude_none:
            data = {k: v for k, v in data.items() if v is not None}
    else:
        raise TypeError('payload must be a pydantic model or dict')

    for key in uuid_fields or set():
        if key in data and data[key] is not None and isinstance(data[key], UUID):
            data[key] = str(data[key])

    for key in enum_fields or set():
        if key in data and data[key] is not None and isinstance(data[key], Enum):
            data[key] = data[key].value

    return data
