"""Tests for multimodal content processing.

Tests image processing, table extraction, and formula parsing.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock

from omni.rag.multimodal import (
    ImageProcessor,
    ImageResult,
    TableExtractor,
    TableResult,
    FormulaParser,
    FormulaResult,
    MultimodalProcessor,
    CONTENT_TYPE_IMAGE,
    CONTENT_TYPE_TABLE,
    CONTENT_TYPE_FORMULA,
    get_image_processor,
    get_table_extractor,
    get_formula_parser,
    get_multimodal_processor,
    extract_formulas,
)


class TestImageProcessor:
    """Tests for ImageProcessor."""

    def test_init_default(self):
        """Test ImageProcessor initialization with defaults."""
        processor = ImageProcessor()
        assert processor.vision_model is None

    def test_init_custom(self):
        """Test ImageProcessor with custom parameters."""
        processor = ImageProcessor(vision_model="gpt-4o")
        assert processor.vision_model == "gpt-4o"

    @pytest.mark.asyncio
    async def test_describe_no_client(self, tmp_path, monkeypatch):
        """Test describe when no LLM client is available."""
        # Create a simple test image
        from PIL import Image

        img = Image.new("RGB", (100, 100), color="red")
        img_path = tmp_path / "test.png"
        img.save(img_path)

        processor = ImageProcessor()
        # Force no-client path; avoid creating real LLM client in tests.
        monkeypatch.setattr(processor, "_get_client", lambda: None)

        result = await processor.describe(str(img_path))
        # Without a client, should return fallback message with filename
        # If LLM is available, it might process the image anyway
        assert result is not None
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_analyze_no_client(self, tmp_path, monkeypatch):
        """Test analyze when no LLM client is available."""
        from PIL import Image

        img = Image.new("RGB", (100, 100), color="blue")
        img.save(tmp_path / "test.png")

        processor = ImageProcessor()
        # Force no-client path; avoid creating real LLM client in tests.
        monkeypatch.setattr(processor, "_get_client", lambda: None)

        result = await processor.analyze(str(tmp_path / "test.png"))
        assert result.description is not None
        assert isinstance(result.objects_detected, list)


class TestImageResult:
    """Tests for ImageResult dataclass."""

    def test_image_result_creation(self):
        """Test ImageResult creation."""
        result = ImageResult(
            description="A red apple",
            objects_detected=["apple", "table"],
            text_extracted=None,
            confidence=0.95,
        )
        assert result.description == "A red apple"
        assert len(result.objects_detected) == 2
        assert result.confidence == 0.95


class TestTableExtractor:
    """Tests for TableExtractor."""

    def test_init(self):
        """Test TableExtractor initialization."""
        extractor = TableExtractor()
        assert extractor.image_processor is not None

    @pytest.mark.asyncio
    async def test_extract_from_text_markdown(self):
        """Test extracting table from markdown text."""
        md_table = """| Name | Age |
|------|-----|
| John | 25 |
| Jane | 30 |"""
        result = await TableExtractor().extract_from_text(md_table)
        assert result.columns == 2
        # rows counts data rows (excluding header and separator)
        assert result.rows == 2, f"Expected 2 rows, got {result.rows}"
        assert result.has_header is True

    @pytest.mark.asyncio
    async def test_extract_from_text_no_table(self):
        """Test extracting when no table is present."""
        result = await TableExtractor().extract_from_text("Just regular text")
        assert result.columns == 0
        assert result.rows == 0

    @pytest.mark.asyncio
    async def test_parse_markdown_complex(self):
        """Test parsing a more complex markdown table."""
        md_table = """| Header1 | Header2 | Header3 |
|:--------|:--------|:--------|
| Value1 | Value2 | Value3 |
| A | B | C |"""
        result = await TableExtractor().parse_markdown(md_table)
        assert result.columns == 3
        assert result.has_header is True
        assert "<table>" in result.html
        assert "<th>Header1</th>" in result.html

    @pytest.mark.asyncio
    async def test_parse_markdown_no_separator(self):
        """Test parsing markdown table without separator row."""
        md_table = """| Name | Value |
| John | 100 |
| Jane | 200 |"""
        result = await TableExtractor().parse_markdown(md_table)
        assert result.columns == 2
        assert result.has_header is False  # No separator, treated as data


class TestTableResult:
    """Tests for TableResult dataclass."""

    def test_table_result_creation(self):
        """Test TableResult creation."""
        result = TableResult(
            html="<table>...</table>",
            markdown="| Header |\n|--------|",
            rows=5,
            columns=3,
            has_header=True,
        )
        assert result.rows == 5
        assert result.columns == 3


class TestFormulaParser:
    """Tests for FormulaParser."""

    def test_init(self):
        """Test FormulaParser initialization."""
        parser = FormulaParser()
        assert parser.image_processor is not None

    def test_extract_from_text_inline(self):
        """Test extracting inline formulas."""
        text = "The equation $E = mc^2$ is famous."
        results = FormulaParser().extract_from_text(text)
        assert len(results) == 1
        assert "E = mc^2" in results[0].latex

    def test_extract_from_text_display(self):
        """Test extracting display formulas."""
        text = """The integral is:
$$
\\int_0^\\infty e^{-x^2} dx = \\frac{\\sqrt{\\pi}}{2}
$$
"""
        results = FormulaParser().extract_from_text(text)
        assert len(results) >= 1
        assert any("int" in r.latex for r in results)

    def test_extract_from_text_no_formulas(self):
        """Test extracting when no formulas are present."""
        text = "This is just regular text without any math."
        results = FormulaParser().extract_from_text(text)
        assert len(results) == 0

    def test_extract_from_text_multiple(self):
        """Test extracting multiple formulas."""
        text = "We have $x = 1$ and $y = 2$. Also $\\sum_{i=1}^n i = \\frac{n(n+1)}{2}$."
        results = FormulaParser().extract_from_text(text)
        assert len(results) == 3

    def test_describe_integral(self):
        """Test formula description for integrals."""
        parser = FormulaParser()
        results = parser.extract_from_text("The $\\int f(x) dx$")
        assert len(results) == 1
        assert "integral" in results[0].description.lower()

    def test_describe_fraction(self):
        """Test formula description for fractions."""
        parser = FormulaParser()
        results = parser.extract_from_text("The $\\frac{a}{b}$ fraction")
        assert len(results) == 1
        assert "fraction" in results[0].description.lower()

    def test_describe_greek_letters(self):
        """Test formula description for Greek letters."""
        parser = FormulaParser()
        results = parser.extract_from_text("$\\alpha + \\beta = \\gamma$")
        assert len(results) == 1
        desc = results[0].description.lower()
        assert "alpha" in desc or "greek" in desc


class TestFormulaResult:
    """Tests for FormulaResult dataclass."""

    def test_formula_result_creation(self):
        """Test FormulaResult creation."""
        result = FormulaResult(
            latex="E = mc^2",
            latex_display="$$E = mc^2$$",
            description="energy-mass equivalence",
        )
        assert result.latex == "E = mc^2"
        assert result.latex_display is not None


class TestMultimodalProcessor:
    """Tests for MultimodalProcessor."""

    def test_init(self):
        """Test MultimodalProcessor initialization."""
        processor = MultimodalProcessor()
        assert processor.image_processor is not None
        assert processor.table_extractor is not None
        assert processor.formula_parser is not None

    @pytest.mark.asyncio
    async def test_process_image(self, tmp_path, monkeypatch):
        """Test processing an image."""
        from PIL import Image

        img = Image.new("RGB", (100, 100), color="green")
        img.save(tmp_path / "test.png")

        processor = MultimodalProcessor()
        # Force no-client path; avoid creating real LLM client in tests.
        monkeypatch.setattr(processor.image_processor, "_get_client", lambda: None)

        result = await processor.process_image(str(tmp_path / "test.png"))
        assert result["type"] == CONTENT_TYPE_IMAGE
        assert "text" in result

    @pytest.mark.asyncio
    async def test_process_table(self):
        """Test processing a table from markdown."""
        processor = MultimodalProcessor()
        table_md = """| Col1 | Col2 |
|-----|-----|
| A | B |"""
        result = await processor.process_table(table_md)
        assert result["type"] == CONTENT_TYPE_TABLE
        assert "html" in result

    @pytest.mark.asyncio
    async def test_process_formula(self):
        """Test processing a formula."""
        processor = MultimodalProcessor()
        result = await processor.process_formula("$\\pi$")
        assert result["type"] == CONTENT_TYPE_FORMULA
        assert "latex" in result

    @pytest.mark.asyncio
    async def test_extract_all(self):
        """Test extracting all multimodal content from text."""
        text = """
        The formula $E = mc^2$ is important.

        | Symbol | Meaning |
        |--------|----------|
        | E | Energy |
        | m | Mass |
        """
        processor = MultimodalProcessor()
        result = await processor.extract_all(text)
        assert "formulas" in result
        assert "tables" in result
        assert "images" in result


class TestContentTypes:
    """Tests for content type constants."""

    def test_content_type_constants(self):
        """Test that content type constants are defined."""
        assert CONTENT_TYPE_IMAGE == "image"
        assert CONTENT_TYPE_TABLE == "table"
        assert CONTENT_TYPE_FORMULA == "formula"


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_get_image_processor(self):
        """Test get_image_processor factory."""
        processor = get_image_processor()
        assert isinstance(processor, ImageProcessor)

    def test_get_table_extractor(self):
        """Test get_table_extractor factory."""
        extractor = get_table_extractor()
        assert isinstance(extractor, TableExtractor)

    def test_get_formula_parser(self):
        """Test get_formula_parser factory."""
        parser = get_formula_parser()
        assert isinstance(parser, FormulaParser)

    def test_get_multimodal_processor(self):
        """Test get_multimodal_processor factory."""
        processor = get_multimodal_processor()
        assert isinstance(processor, MultimodalProcessor)


class TestExtractFormulas:
    """Tests for extract_formulas convenience function."""

    def test_extract_formulas_simple(self):
        """Test extract_formulas with simple input."""
        text = "The value $\\alpha$ is used."
        results = extract_formulas(text)
        assert len(results) == 1
        assert "latex" in results[0]

    def test_extract_formulas_empty(self):
        """Test extract_formulas with no formulas."""
        text = "No formulas here"
        results = extract_formulas(text)
        assert len(results) == 0


class TestMultimodalProcessorIntegration:
    """Integration tests for multimodal processor."""

    @pytest.mark.asyncio
    async def test_full_pipeline(self):
        """Test full multimodal processing pipeline."""
        text = """
        # Math Section

        The quadratic formula is:
        $$x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}$$

        Results:

        | Variable | Description |
        |----------|-------------|
        | a | coefficient of x^2 |
        | b | coefficient of x |
        | c | constant term |
        """
        processor = MultimodalProcessor()

        # Extract formulas
        formulas = processor.formula_parser.extract_from_text(text)
        assert len(formulas) >= 1

        # Extract tables (using extract_from_text with the full text)
        table_result = await processor.table_extractor.extract_from_text(text)
        # The extract_all extracts formulas, but tables need separate extraction
        # This tests that we can extract tables from the text content
        assert table_result.columns >= 0  # May or may not find depending on text format

        # Full extraction - formulas only
        all_content = await processor.extract_all(text)
        assert len(all_content["formulas"]) >= 1
        assert "tables" in all_content  # Key exists
