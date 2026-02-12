"""
multimodal.py - Multimodal Content Processing

Provides image, table, and formula processing for RAG documents:
- ImageProcessor: Extract descriptions from images using VLM
- TableExtractor: Parse and structure tabular data
- FormulaParser: Extract and convert LaTeX formulas

Usage:
    from omni.rag.multimodal import ImageProcessor, TableExtractor

    # Process image
    processor = ImageProcessor()
    description = await processor.describe("image.png")

    # Extract table
    extractor = TableExtractor()
    table_html, table_md = await extractor.extract("table.png")
"""

from __future__ import annotations

import asyncio
import base64
import json
import re
import structlog
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image

logger = structlog.get_logger(__name__)


# Content block types
CONTENT_TYPE_IMAGE = "image"
CONTENT_TYPE_TABLE = "table"
CONTENT_TYPE_FORMULA = "formula"
CONTENT_TYPE_TEXT = "text"


@dataclass
class ImageResult:
    """Result of image processing."""

    description: str
    objects_detected: list[str]
    text_extracted: str | None
    confidence: float


@dataclass
class TableResult:
    """Result of table extraction."""

    html: str
    markdown: str
    rows: int
    columns: int
    has_header: bool


@dataclass
class FormulaResult:
    """Result of formula extraction."""

    latex: str
    latex_display: str | None
    description: str


class ImageProcessor:
    """Process images and extract information using Vision-Language Models.

    Supports:
    - General image description
    - Object detection
    - OCR (text extraction from images)
    - Diagram understanding
    """

    def __init__(
        self,
        vision_model: str | None = None,
        api_key: str | None = None,
    ):
        """
        Initialize the image processor.

        Args:
            vision_model: VLM model name (default: from config)
            api_key: API key for the vision model
        """
        self.vision_model = vision_model
        self.api_key = api_key
        self._client = None

    def _get_client(self) -> Any:
        """Get or create the vision model client."""
        if self._client is None:
            try:
                from omni.foundation.services.llm import InferenceClient

                self._client = InferenceClient()
            except ImportError:
                logger.warning("No LLM client available for image processing")
        return self._client

    def _encode_image(self, image_path: str) -> str:
        """Encode image to base64 for API calls."""
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        with Image.open(path) as img:
            # Resize if too large (max 2048px)
            max_size = 2048
            if max(img.size) > max_size:
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

            # Convert to RGB if necessary
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            buffer = BytesIO()
            img.save(buffer, format="JPEG", quality=85)
            return base64.b64encode(buffer.getvalue()).decode("utf-8")

    async def describe(
        self,
        image_path: str,
        prompt: str | None = None,
    ) -> str:
        """
        Generate a description of an image.

        Args:
            image_path: Path to the image file
            prompt: Optional custom prompt for description

        Returns:
            Text description of the image
        """
        client = self._get_client()
        if client is None:
            return f"[Image: {Path(image_path).name}]"

        try:
            base64_image = await asyncio.to_thread(self._encode_image, image_path)

            default_prompt = (
                "Describe this image in detail. Include any text visible, "
                "objects, diagrams, charts, or visual content relevant for "
                "understanding a technical document."
            )
            prompt = prompt or default_prompt

            # Call vision model
            response = await client.complete(
                system_prompt="You are a vision assistant for technical documents.",
                user_query=f"{prompt}\n\nImage: data:image/jpeg;base64,{base64_image}",
            )

            if isinstance(response, dict):
                return response.get("text", "") or str(response)
            return str(response)

        except Exception as e:
            logger.error("Image description failed", error=str(e))
            return f"[Image: {Path(image_path).name}]"

    async def extract_text(self, image_path: str) -> str:
        """
        Extract text from an image using OCR.

        Args:
            image_path: Path to the image

        Returns:
            Extracted text content
        """
        client = self._get_client()
        if client is None:
            return ""

        try:
            base64_image = await asyncio.to_thread(self._encode_image, image_path)

            response = await client.complete(
                system_prompt="You are an OCR system. Extract all text from the image verbatim.",
                user_query=f"Extract all text from this image:\n\nImage: data:image/jpeg;base64,{base64_image}",
            )

            if isinstance(response, dict):
                return response.get("text", "") or str(response)
            return str(response)

        except Exception as e:
            logger.error("OCR failed", error=str(e))
            return ""

    async def analyze(self, image_path: str) -> ImageResult:
        """
        Perform full image analysis.

        Args:
            image_path: Path to the image

        Returns:
            ImageResult with description, objects, and extracted text
        """
        client = self._get_client()
        if client is None:
            return ImageResult(
                description=f"[Image: {Path(image_path).name}]",
                objects_detected=[],
                text_extracted=None,
                confidence=0.0,
            )

        try:
            base64_image = await asyncio.to_thread(self._encode_image, image_path)

            response = await client.complete(
                system_prompt="""You are a vision analysis system. Analyze the image and return JSON:
{
    "description": "detailed description",
    "objects": ["list", "of", "objects"],
    "text": "extracted text or null",
    "confidence": 0.0-1.0
}""",
                user_query=f"Analyze this image:\n\nImage: data:image/jpeg;base64,{base64_image}",
            )

            # Parse response
            if isinstance(response, dict):
                return ImageResult(
                    description=response.get("description", ""),
                    objects_detected=response.get("objects", []),
                    text_extracted=response.get("text"),
                    confidence=response.get("confidence", 0.8),
                )

            # Try to parse JSON from text
            try:
                json_match = re.search(r"\{[^{}]+\}", str(response))
                if json_match:
                    data = json.loads(json_match.group())
                    return ImageResult(
                        description=data.get("description", ""),
                        objects_detected=data.get("objects", []),
                        text_extracted=data.get("text"),
                        confidence=data.get("confidence", 0.8),
                    )
            except (json.JSONDecodeError, AttributeError):
                pass

            return ImageResult(
                description=str(response)[:500],
                objects_detected=[],
                text_extracted=None,
                confidence=0.5,
            )

        except Exception as e:
            logger.error("Image analysis failed", error=str(e))
            return ImageResult(
                description=f"[Image analysis failed: {Path(image_path).name}]",
                objects_detected=[],
                text_extracted=None,
                confidence=0.0,
            )


class TableExtractor:
    """Extract and structure tabular data from images or documents.

    Supports:
    - Markdown table parsing
    - HTML table extraction
    - Image-based table OCR
    - CSV/TSV conversion
    """

    def __init__(self, processor: ImageProcessor | None = None):
        """
        Initialize the table extractor.

        Args:
            processor: Optional ImageProcessor for image-based extraction
        """
        self.image_processor = processor or ImageProcessor()

    async def extract_from_image(self, image_path: str) -> TableResult:
        """
        Extract table data from an image.

        Args:
            image_path: Path to the table image

        Returns:
            TableResult with structured table data
        """
        description = await self.image_processor.describe(image_path)

        # Parse markdown table from description
        return await self.parse_markdown(description)

    async def extract_from_text(self, text: str) -> TableResult:
        """
        Extract table from markdown or text content.

        Args:
            text: Text containing table data

        Returns:
            TableResult with structured table data
        """
        return await self.parse_markdown(text)

    async def parse_markdown(self, text: str) -> TableResult:
        """
        Parse a markdown table into structured data.

        Args:
            text: Markdown table or text containing table

        Returns:
            TableResult with parsed table
        """
        # Find markdown table pattern
        table_pattern = r"\|[\s\S]*?(?:\n\|[\s\-:|]+[\s\S]*?)?(?=\n\n|\n[^|]|$)"
        matches = re.findall(table_pattern, text)

        if not matches:
            # Return empty result
            return TableResult(
                html="",
                markdown="",
                rows=0,
                columns=0,
                has_header=False,
            )

        table_md = matches[0].strip()
        lines = [l for l in table_md.split("\n") if l.strip().startswith("|")]

        if len(lines) < 2:
            return TableResult(
                html="",
                markdown="",
                rows=0,
                columns=0,
                has_header=False,
            )

        # Parse columns from first row
        header_cols = [c.strip() for c in lines[0].split("|")[1:-1]]
        columns = len(header_cols)

        # Check for separator row
        has_header = len(lines) > 1 and re.match(r"^[\s|\-:]+\|$", lines[1]) is not None

        # Count data rows (excluding header and separator row)
        if has_header:
            rows = len(lines) - 2  # Exclude header and separator
        else:
            rows = len(lines) - 1  # Exclude first "header" row

        # Convert to HTML
        html_parts = ["<table>"]
        if has_header:
            html_parts.append("<thead><tr>")
            for col in header_cols:
                html_parts.append(f"<th>{col}</th>")
            html_parts.append("</tr></thead>")
            html_parts.append("<tbody>")
            data_start = 2
        else:
            html_parts.append("<thead><tr>")
            for col in header_cols:
                html_parts.append(f"<th>{col}</th>")
            html_parts.append("</tr></thead>")
            html_parts.append("<tbody>")
            data_start = 1

        for line in lines[data_start:]:
            cols = [c.strip() for c in line.split("|")[1:-1]]
            html_parts.append("<tr>")
            for i, col in enumerate(cols):
                tag = "th" if i == 0 and not has_header else "td"
                html_parts.append(f"<{tag}>{col}</{tag}>")
            html_parts.append("</tr>")

        html_parts.append("</tbody></table>")
        html = "".join(html_parts)

        return TableResult(
            html=html,
            markdown=table_md,
            rows=rows,
            columns=columns,
            has_header=has_header,
        )


class FormulaParser:
    """Extract and process mathematical formulas.

    Supports:
    - LaTeX formula detection
    - Inline vs display math distinction
    - Formula description generation
    """

    # LaTeX patterns
    INLINE_PATTERN = re.compile(r"\$([^\$]+)\$")
    DISPLAY_PATTERN = re.compile(r"\$\$([^\$]+)\$\$")
    ENV_PATTERN = re.compile(r"\\begin\{(\w+)\}([\s\S]*?)\\end\{\1\}")

    def __init__(self, processor: ImageProcessor | None = None):
        """
        Initialize the formula parser.

        Args:
            processor: Optional ImageProcessor for image-based extraction
        """
        self.image_processor = processor or ImageProcessor()

    def extract_from_text(self, text: str) -> list[FormulaResult]:
        """
        Extract all formulas from text.

        Args:
            text: Text containing LaTeX formulas

        Returns:
            List of FormulaResult objects
        """
        results = []

        # Extract display formulas ($$...$$)
        for match in self.DISPLAY_PATTERN.finditer(text):
            latex = match.group(1).strip()
            results.append(
                FormulaResult(
                    latex=latex,
                    latex_display=f"$${latex}$$",
                    description=self._describe_formula(latex),
                )
            )

        # Extract inline formulas ($...$)
        # Be careful not to double-match display formulas
        remaining = self.DISPLAY_PATTERN.sub("", text)
        for match in self.INLINE_PATTERN.finditer(remaining):
            latex = match.group(1).strip()
            results.append(
                FormulaResult(
                    latex=latex,
                    latex_display=None,
                    description=self._describe_formula(latex),
                )
            )

        # Extract environments
        for match in self.ENV_PATTERN.finditer(text):
            env_name = match.group(1)
            content = match.group(2).strip()
            latex = f"\\begin{{{env_name}}}{content}\\end{{{env_name}}}"
            results.append(
                FormulaResult(
                    latex=latex,
                    latex_display=f"$${latex}$$",
                    description=self._describe_formula(latex),
                )
            )

        return results

    def _describe_formula(self, latex: str) -> str:
        """
        Generate a human-readable description of a formula.

        Args:
            latex: LaTeX formula

        Returns:
            Description of what the formula represents
        """
        # Common patterns
        descriptions = []

        # Integrals
        if "\\int" in latex:
            descriptions.append("integral")
            if r"\iint" in latex:
                descriptions.append("double integral")
            if r"\iiint" in latex:
                descriptions.append("triple integral")
            if r"\oint" in latex:
                descriptions.append("contour integral")

        # Sums
        if "\\sum" in latex:
            descriptions.append("summation")

        # Products
        if "\\prod" in latex:
            descriptions.append("product")

        # Limits
        if "\\lim" in latex:
            descriptions.append("limit")

        # Derivatives
        if "\\frac{d" in latex or "\\partial" in latex:
            descriptions.append("derivative")
        if "\\nabla" in latex:
            descriptions.append("gradient-related")

        # Greek letters (common ones)
        greek = {
            "\\alpha": "alpha",
            "\\beta": "beta",
            "\\gamma": "gamma",
            "\\delta": "delta",
            "\\epsilon": "epsilon",
            "\\theta": "theta",
            "\\lambda": "lambda",
            "\\mu": "mu",
            "\\pi": "pi",
            "\\sigma": "sigma",
            "\\omega": "omega",
            "\\Delta": "Delta",
            "\\Omega": "Omega",
        }
        found_greek = [v for k, v in greek.items() if k in latex]
        if found_greek:
            descriptions.append(f"contains: {', '.join(found_greek)}")

        # Fractions
        if "\\frac" in latex:
            descriptions.append("fraction")

        # Powers and roots
        if "\\sqrt" in latex:
            descriptions.append("root")
        if "^" in latex:
            descriptions.append("exponentiation")

        # Matrices
        if "\\begin{matrix}" in latex or "\\begin{pmatrix}" in latex:
            descriptions.append("matrix")
        if "\\begin{bmatrix}" in latex:
            descriptions.append("matrix (bracket)")

        if descriptions:
            return ", ".join(descriptions)
        return "mathematical expression"

    async def extract_from_image(self, image_path: str) -> list[FormulaResult]:
        """
        Extract formula from an image.

        Args:
            image_path: Path to the formula image

        Returns:
            List of FormulaResult objects
        """
        client = self.image_processor._get_client()
        if client is None:
            return []

        try:
            base64_image = await asyncio.to_thread(self.image_processor._encode_image, image_path)

            response = await client.complete(
                system_prompt="""You are a formula recognition system. Extract LaTeX from the image.
Return the LaTeX code that represents any mathematical formulas visible.
If no formulas, return 'NONE'.""",
                user_query=f"Extract LaTeX formulas:\n\nImage: data:image/jpeg;base64,{base64_image}",
            )

            text = str(response)
            if text.strip().upper() == "NONE":
                return []

            return self.extract_from_text(text)

        except Exception as e:
            logger.error("Formula extraction from image failed", error=str(e))
            return []


class MultimodalProcessor:
    """Unified multimodal content processor.

    Combines image, table, and formula processing.
    """

    def __init__(
        self,
        image_processor: ImageProcessor | None = None,
        table_extractor: TableExtractor | None = None,
        formula_parser: FormulaParser | None = None,
    ):
        """
        Initialize the multimodal processor.

        Args:
            image_processor: Optional ImageProcessor instance
            table_extractor: Optional TableExtractor instance
            formula_parser: Optional FormulaParser instance
        """
        self.image_processor = image_processor or ImageProcessor()
        self.table_extractor = table_extractor or TableExtractor(self.image_processor)
        self.formula_parser = formula_parser or FormulaParser(self.image_processor)

    async def process_image(self, image_path: str) -> dict[str, Any]:
        """
        Process an image file.

        Args:
            image_path: Path to the image

        Returns:
            Content block dict with image data
        """
        result = await self.image_processor.analyze(image_path)

        return {
            "type": CONTENT_TYPE_IMAGE,
            "text": result.description,
            "source": str(image_path),
            "metadata": {
                "objects": result.objects_detected,
                "extracted_text": result.text_extracted,
                "confidence": result.confidence,
            },
        }

    async def process_table(self, source: str | Path) -> dict[str, Any]:
        """
        Process a table from text or image.

        Args:
            source: Table text or image path

        Returns:
            Content block dict with table data
        """
        if isinstance(source, Path) or (isinstance(source, str) and Path(source).exists()):
            result = await self.table_extractor.extract_from_image(str(source))
        else:
            result = await self.table_extractor.extract_from_text(str(source))

        return {
            "type": CONTENT_TYPE_TABLE,
            "text": result.markdown,
            "html": result.html,
            "source": str(source),
            "metadata": {
                "rows": result.rows,
                "columns": result.columns,
                "has_header": result.has_header,
            },
        }

    async def process_formula(self, source: str | Path) -> dict[str, Any]:
        """
        Process a formula from text or image.

        Args:
            source: Formula text or image path

        Returns:
            Content block dict with formula data
        """
        if isinstance(source, Path) or (isinstance(source, str) and Path(source).exists()):
            results = await self.formula_parser.extract_from_image(str(source))
        else:
            results = self.formula_parser.extract_from_text(str(source))

        if not results:
            return {
                "type": CONTENT_TYPE_FORMULA,
                "text": "",
                "latex": "",
                "source": str(source),
                "metadata": {},
            }

        # Return the first formula
        formula = results[0]
        return {
            "type": CONTENT_TYPE_FORMULA,
            "text": formula.description,
            "latex": formula.latex,
            "latex_display": formula.latex_display,
            "source": str(source),
            "metadata": {},
        }

    async def extract_all(self, content: str) -> dict[str, Any]:
        """
        Extract all multimodal content from text.

        Args:
            content: Text that may contain formulas

        Returns:
            Dict with separate lists for images, tables, formulas
        """
        formulas = self.formula_parser.extract_from_text(content)

        return {
            "images": [],
            "tables": [],
            "formulas": [
                {
                    "latex": f.latex,
                    "display": f.latex_display,
                    "description": f.description,
                }
                for f in formulas
            ],
        }


# Convenience functions
def get_image_processor() -> ImageProcessor:
    """Get an ImageProcessor instance."""
    return ImageProcessor()


def get_table_extractor() -> TableExtractor:
    """Get a TableExtractor instance."""
    return TableExtractor()


def get_formula_parser() -> FormulaParser:
    """Get a FormulaParser instance."""
    return FormulaParser()


def get_multimodal_processor() -> MultimodalProcessor:
    """Get a MultimodalProcessor instance."""
    return MultimodalProcessor()


async def process_image(image_path: str) -> dict[str, Any]:
    """Process a single image file."""
    processor = get_multimodal_processor()
    return await processor.process_image(image_path)


async def process_table(source: str) -> dict[str, Any]:
    """Process a table from text or image path."""
    processor = get_multimodal_processor()
    return await processor.process_table(source)


async def process_formula(source: str) -> dict[str, Any]:
    """Process a formula from text or image path."""
    processor = get_multimodal_processor()
    return await processor.process_formula(source)


def extract_formulas(text: str) -> list[dict[str, str]]:
    """Extract all formulas from text."""
    parser = get_formula_parser()
    formulas = parser.extract_from_text(text)
    return [{"latex": f.latex, "description": f.description} for f in formulas]


__all__ = [
    "ImageProcessor",
    "ImageResult",
    "TableExtractor",
    "TableResult",
    "FormulaParser",
    "FormulaResult",
    "MultimodalProcessor",
    "CONTENT_TYPE_IMAGE",
    "CONTENT_TYPE_TABLE",
    "CONTENT_TYPE_FORMULA",
    "get_image_processor",
    "get_table_extractor",
    "get_formula_parser",
    "get_multimodal_processor",
    "process_image",
    "process_table",
    "process_formula",
    "extract_formulas",
]
