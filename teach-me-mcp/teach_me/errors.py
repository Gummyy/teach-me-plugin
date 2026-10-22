"""Errors raised by the tools.

A `ToolError` is sent back to the model as a tool error with its message, so the
message must tell the model how to fix its call.
"""

from fastmcp.exceptions import ToolError

__all__ = ["ToolError"]
