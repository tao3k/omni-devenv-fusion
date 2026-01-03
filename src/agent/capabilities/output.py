"""
src/agent/capabilities/output.py
Output Formatting Tools - MCP工具输出美化

提供 MCP 工具返回数据的格式化输出：
- pretty_json: 美化 JSON 输出（使用 bat 或 Python）
- pretty_dict: 美化 Python dict 输出

Philosophy:
- 输出应该 human-readable
- 自动检测并使用系统工具 (bat) 进行语法高亮
- 无感知集成，不需要额外配置

Usage:
    from agent.capabilities.output import register_output_tools
    mcp = FastMCP(...)
    register_output_tools(mcp)
"""
from __future__ import annotations

import json
import subprocess
from typing import Any

from mcp.server.fastmcp import FastMCP
import structlog

logger = structlog.get_logger(__name__)


def _is_bat_installed() -> bool:
    """检查系统是否安装了 bat 工具。"""
    try:
        subprocess.run(
            ["bat", "--version"],
            capture_output=True,
            check=True,
            timeout=5
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _format_with_bat(content: str, language: str = "json") -> str:
    """使用 bat 美化输出。"""
    try:
        result = subprocess.run(
            ["bat", "--language", language, "--style", "plain", "--color", "always"],
            input=content.encode(),
            capture_output=True,
            check=True,
            timeout=10
        )
        return result.stdout.decode()
    except subprocess.CalledProcessError as e:
        return f"Error with bat: {e}\n{content}"


def _format_with_python(content: str, indent: int = 2) -> str:
    """使用 Python json 模块美化输出。"""
    try:
        parsed = json.loads(content)
        return json.dumps(parsed, indent=indent, ensure_ascii=False, sort_keys=True)
    except json.JSONDecodeError as e:
        return f"Invalid JSON: {e}\n\nOriginal content:\n{content}"


def register_output_tools(mcp: FastMCP) -> None:
    """Register all output formatting tools with the MCP server."""

    @mcp.tool()
    async def pretty_json(data: dict) -> str:
        """
        美化 JSON 字典输出。

        自动检测系统是否安装 bat：
        - 如果安装了 bat：使用 bat 进行语法高亮
        - 否则：使用 Python json 模块美化

        Args:
            data: 要美化的 Python 字典

        Returns:
            美化后的 JSON 字符串（带颜色高亮）

        Example:
            pretty_json({"name": "test", "version": "1.0.0"})
            # 输出带语法高亮的 JSON
        """
        # 序列化为 JSON 字符串
        json_str = json.dumps(data, indent=2, ensure_ascii=False)

        # 尝试使用 bat 美化
        if _is_bat_installed():
            return _format_with_bat(json_str, "json")
        else:
            return json_str

    @mcp.tool()
    async def pretty_output(
        content: str,
        format_type: str = "json",
        indent: int = 2
    ) -> str:
        """
        通用输出格式化工具。

        支持格式化 JSON、YAML、TOML 等格式。

        Args:
            content: 要格式化的原始字符串内容
            format_type: 格式类型 (json, yaml, xml, toml)
            indent: 缩进空格数 (默认: 2)

        Returns:
            格式化后的字符串

        Example:
            pretty_output('{"name":"test"}', format_type="json")
            pretty_output('name: test\\nversion: 1.0.0', format_type="yaml")
        """
        if format_type == "json":
            try:
                parsed = json.loads(content)
                formatted = json.dumps(parsed, indent=indent, ensure_ascii=False)

                if _is_bat_installed():
                    return _format_with_bat(formatted, "json")
                return formatted
            except json.JSONDecodeError as e:
                return f"JSON Parse Error: {e}\n\nOriginal:\n{content}"

        elif format_type == "yaml":
            # YAML 格式化（简单处理：尝试用 bat）
            if _is_bat_installed():
                return _format_with_bat(content, "yaml")
            return content

        elif format_type == "xml":
            if _is_bat_installed():
                return _format_with_bat(content, "xml")
            return content

        else:
            # 未知格式，直接返回
            if _is_bat_installed():
                return _format_with_bat(content, format_type)
            return content

    @mcp.tool()
    async def format_mcp_response(response: dict) -> str:
        """
        格式化 MCP 响应数据为人类可读格式。

        专门用于格式化 MCP 工具的返回数据，自动美化嵌套结构。

        Args:
            response: MCP 工具返回的字典

        Returns:
            美化后的字符串，Markdown 格式

        Example:
            format_mcp_response({
                "success": True,
                "results": [...],
                "count": 5
            })
        """
        # 美化 JSON
        json_str = json.dumps(response, indent=2, ensure_ascii=False)

        if _is_bat_installed():
            formatted = _format_with_bat(json_str, "json")
        else:
            formatted = json_str

        # 添加 Markdown 包装
        markdown = f"""```json
{formatted}
```"""
        return markdown

    @mcp.tool()
    async def view_structured_data(
        title: str,
        data: dict,
        show_metadata: bool = True
    ) -> str:
        """
        以美观的表格/列表形式查看结构化数据。

        自动格式化：
        - 列表：编号列表
        - 字典：键值对表格
        - 嵌套结构：分层缩进

        Args:
            title: 数据标题
            data: 要显示的数据
            show_metadata: 是否显示元数据

        Returns:
            Markdown 格式的格式化输出
        """
        lines = [f"## {title}", ""]

        def format_value(value: Any, indent: int = 0) -> list[str]:
            """递归格式化值。"""
            prefix = "  " * indent

            if isinstance(value, dict):
                result = []
                for k, v in value.items():
                    if isinstance(v, (dict, list)) and v:
                        result.append(f"{prefix}- **{k}**:")
                        result.extend(format_value(v, indent + 1))
                    else:
                        result.append(f"{prefix}- **{k}**: {v}")
                return result
            elif isinstance(value, list):
                if not value:
                    return [f"{prefix}- (empty)"]
                result = []
                for i, item in enumerate(value):
                    if isinstance(item, (dict, list)):
                        result.append(f"{prefix}- Item {i + 1}:")
                        result.extend(format_value(item, indent + 1))
                    else:
                        result.append(f"{prefix}- {item}")
                return result
            else:
                return [f"{prefix}{value}"]

        lines.extend(format_value(data))
        lines.append("")

        return "\n".join(lines)

    logger.info("Output formatting tools registered")


__all__ = [
    "register_output_tools",
]
