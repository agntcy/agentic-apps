# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
A2UI JSON Schema Definition.
"""

A2UI_SCHEMA = """
{
  "type": "array",
  "items": {
    "type": "object",
    "properties": {
      "operation": {
        "type": "string",
        "enum": ["render", "update", "append", "delete"]
      },
      "surfaceId": {
        "type": "string"
      },
      "componentName": {
        "type": "string"
      },
      "data": {
        "type": "object"
      },
      "dataModelUpdate": {
        "type": "object"
      }
    },
    "required": ["operation"]
  }
}
"""
