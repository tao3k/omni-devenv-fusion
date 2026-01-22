"""
JSON-RPC 2.0 Message Types

Pydantic models with orjson serialization for maximum compatibility and performance.
Updated for ODF-EP v6.0:
- Uses Foundation OrjsonModel for 10x faster serialization
- Unified with Trinity Architecture
"""

from typing import Any, Optional, Union
from enum import Enum

import orjson

from omni.foundation.api.types import OrjsonModel


class MessageType(Enum):
    """Type of JSON-RPC message."""

    REQUEST = "request"
    NOTIFICATION = "notification"
    RESPONSE = "response"


class JSONRPCRequest(OrjsonModel):
    """JSON-RPC 2.0 Request message."""

    jsonrpc: str = "2.0"
    method: str = ""
    params: Optional[Union[dict[str, Any], list[Any]]] = None
    id: Optional[Union[str, int]] = None

    @property
    def is_notification(self) -> bool:
        """Check if this is a notification (no id)."""
        return self.id is None

    @property
    def message_type(self) -> MessageType:
        """Get the message type."""
        if self.id is None:
            return MessageType.NOTIFICATION
        return MessageType.REQUEST

    def model_dump_dict(self) -> dict[str, Any]:
        """Serialize to dict for orjson."""
        return self.model_dump(exclude_none=True)


class JSONRPCResponse(OrjsonModel):
    """JSON-RPC 2.0 Response message."""

    jsonrpc: str = "2.0"
    result: Optional[Any] = None
    error: Optional[dict[str, Any]] = None
    id: Optional[Union[str, int]] = None

    @property
    def is_error(self) -> bool:
        """Check if this is an error response."""
        return self.error is not None

    def model_dump_dict(self) -> dict[str, Any]:
        """Serialize to dict for orjson."""
        return self.model_dump(exclude_none=True)


class JSONRPCError(OrjsonModel):
    """JSON-RPC 2.0 Error object."""

    code: int
    message: str
    data: Optional[Any] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.data is not None:
            result["data"] = self.data
        return result

    @classmethod
    def parse(cls, error_dict: dict[str, Any]) -> "JSONRPCError":
        """Parse error from dictionary."""
        return cls(
            code=error_dict.get("code", -1),
            message=error_dict.get("message", "Unknown Error"),
            data=error_dict.get("data"),
        )

    def model_dump_dict(self) -> dict[str, Any]:
        """Serialize to dict for orjson."""
        return self.to_dict()


# Standard JSON-RPC error codes
class ErrorCode:
    """Standard JSON-RPC 2.0 error codes."""

    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    SERVER_ERROR = -32000


# MCP-specific error codes (extension to JSON-RPC)
class MCPErrorCode:
    """MCP protocol-specific error codes."""

    # Tool errors (-32000 to -32099)
    TOOL_NOT_FOUND = -32001
    TOOL_EXECUTION_ERROR = -32002
    TOOL_PARAM_INVALID = -32003

    # Resource errors (-32100 to -32199)
    RESOURCE_NOT_FOUND = -32100
    RESOURCE_INVALID = -32101
    RESOURCE_READ_ERROR = -32102

    # Prompt errors (-32200 to -32299)
    PROMPT_NOT_FOUND = -32200
    PROMPT_INVALID = -32201

    # Session errors (-32300 to -32399)
    SESSION_NOT_INITIALIZED = -32300
    SESSION_LIMIT_EXCEEDED = -32301


def make_mcp_error_response(
    id: Optional[Union[str, int]],
    code: int,
    message: str,
    data: Optional[Any] = None,
) -> JSONRPCResponse:
    """Factory for MCP error responses."""
    return make_error_response(id=id, code=code, message=message, data=data)


def make_error_response(
    id: Optional[Union[str, int]],
    code: int,
    message: str,
    data: Optional[Any] = None,
) -> JSONRPCResponse:
    """Factory for error responses."""
    return JSONRPCResponse(
        jsonrpc="2.0",
        error=JSONRPCError(code=code, message=message, data=data).to_dict(),
        id=id,
    )


def make_success_response(
    id: Optional[Union[str, int]],
    result: Any,
) -> JSONRPCResponse:
    """Factory for success responses."""
    return JSONRPCResponse(jsonrpc="2.0", result=result, id=id)


# JSON serialization helpers using orjson
def json_dumps(obj: dict[str, Any]) -> bytes:
    """Serialize dict to JSON bytes using orjson."""
    return orjson.dumps(obj)


def json_loads(data: bytes | str) -> dict[str, Any]:
    """Deserialize JSON bytes/dict to dict."""
    if isinstance(data, str):
        data = data.encode()
    return orjson.loads(data)
