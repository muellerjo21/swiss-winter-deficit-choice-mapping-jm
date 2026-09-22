def scale_attribute(raw_value: float, attribute: str) -> float:
    """Scale a raw (decimal) attribute value to the 0-1 scale the model was fitted on."""
    from config import ATTRIBUTE_MAX_VALUES
    return raw_value / ATTRIBUTE_MAX_VALUES[attribute]