"""Utilities for outputting results to file."""
from __future__ import annotations

import json


def write_to_file(xml_dict: dict, path: str) -> None:
    """Write the parse results to file for debugging."""
    json_object = json.dumps(xml_dict, indent=4, default=str)
    with open(
        path,
        "w",
        encoding="utf-8",
    ) as outfile:
        outfile.write(json_object)
