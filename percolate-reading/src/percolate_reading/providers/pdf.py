"""PDF parser using Kreuzberg with structured outputs.

Based on carrier.parsers.pdf with async support.
Implements hybrid semantic + visual verification strategy:
1. Kreuzberg extracts content with page references
2. Quality flags identify elements needing verification
3. Claude vision can verify specific pages on-demand (future)
"""

import json
from pathlib import Path
from typing import Callable
from uuid import UUID

from kreuzberg import ExtractionConfig, extract_file_sync
from loguru import logger

from percolate_reading.models.parse import (
    ParseContent,
    ParseQuality,
    ParseResult,
    ParseStorage,
    ParsedTable,
    QualityFlag,
    StorageStrategy,
)
from percolate_reading.providers.base import ParseProvider
from percolate_reading.storage.manager import StorageManager


class PDFProvider(ParseProvider):
    """Parse PDF documents to structured outputs with page references.

    Uses Kreuzberg for fast semantic extraction:
    - ~2s per document (local processing)
    - Best-effort table extraction
    - Quality flags for uncertain content
    """

    def __init__(self, storage_manager: StorageManager):
        """Initialize PDF provider.

        Args:
            storage_manager: Storage manager for artifacts
        """
        super().__init__(storage_manager)

    @property
    def supported_types(self) -> list[str]:
        """Supported MIME types."""
        return ["application/pdf"]

    @property
    def provider_name(self) -> str:
        """Provider name."""
        return "kreuzberg_pdf"

    async def _parse(
        self,
        file_path: Path,
        job_id: UUID,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> ParseResult:
        """Parse PDF content using Kreuzberg.

        Args:
            file_path: Path to PDF file
            job_id: Job ID for artifact storage
            progress_callback: Optional progress callback

        Returns:
            ParseResult with extracted content and metadata

        Raises:
            Exception: On parsing failure
        """
        if progress_callback:
            progress_callback(0.1, "Initializing PDF extraction")

        # Configure Kreuzberg for optimal extraction
        config = self._get_default_config()

        if progress_callback:
            progress_callback(0.2, "Extracting PDF content")

        # Extract content (synchronous - Kreuzberg doesn't support async yet)
        kreuzberg_result = extract_file_sync(file_path, config=config)

        if progress_callback:
            progress_callback(0.6, "Processing tables and images")

        # Build structured result with table quality assessment
        parse_result = await self._build_parse_result(
            kreuzberg_result, file_path, job_id, progress_callback
        )

        if progress_callback:
            progress_callback(0.9, "Writing artifacts")

        # Store artifacts
        await self._store_artifacts(parse_result, job_id, progress_callback)

        logger.info(
            f"Extracted PDF content. "
            f"Found {parse_result.content.num_tables} tables, "
            f"{parse_result.quality.needs_verification} needs verification"
        )

        if progress_callback:
            progress_callback(1.0, "Parsing complete")

        return parse_result

    def _get_default_config(self) -> ExtractionConfig:
        """Get optimized extraction configuration.

        Returns:
            ExtractionConfig for Kreuzberg
        """
        return ExtractionConfig(
            # Disable table extraction - GMFT not installed
            # TODO: Add gmft dependency and re-enable table extraction
            extract_tables=False,
            # Content processing
            chunk_content=False,  # Keep document structure intact
            # Entity extraction (requires kreuzberg[entity-extraction])
            extract_keywords=False,  # Disabled to avoid additional dependency
        )

    async def _build_parse_result(
        self,
        kreuzberg_result,
        file_path: Path,
        job_id: UUID,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> ParseResult:
        """Convert Kreuzberg result to structured ParseResult.

        Args:
            kreuzberg_result: Result from Kreuzberg extraction
            file_path: Original file path
            job_id: Job ID
            progress_callback: Optional progress callback

        Returns:
            ParseResult with structured data
        """
        # Extract tables with quality assessment
        tables: list[ParsedTable] = []
        for i, table_data in enumerate(kreuzberg_result.tables):
            quality_flags, confidence = self._assess_table_quality(table_data)

            # TODO: Save cropped table image if available
            cropped_path = None
            # if "cropped_image" in table_data and table_data["cropped_image"]:
            #     cropped_path = self._save_table_image(
            #         table_data["cropped_image"], file_path.stem, i, job_id
            #     )

            parsed_table = ParsedTable(
                id=f"table_{i}",
                page_number=table_data.get("page_number", 0),
                text=table_data.get("text", ""),
                row_count=len(table_data.get("df", [])) if "df" in table_data else 0,
                column_count=(
                    len(table_data["df"].columns)
                    if "df" in table_data and hasattr(table_data["df"], "columns")
                    else None
                ),
                confidence=confidence,
                flags=[f.value for f in quality_flags],
                cropped_image_path=cropped_path,
            )
            tables.append(parsed_table)

        # Extract page count from metadata
        page_count = 0
        summary = kreuzberg_result.metadata.get("summary", "")
        if "pages" in summary:
            # Parse "PDF document with 36 pages."
            try:
                parts = summary.split()
                if "with" in parts:
                    page_count = int(parts[parts.index("with") + 1])
            except (ValueError, IndexError):
                logger.warning(f"Could not parse page count from: {summary}")

        # Assess overall quality
        overall_quality = self._assess_overall_quality(tables)

        # Create storage info (will be populated when artifacts are written)
        storage = ParseStorage(
            strategy=self._current_job.storage_strategy if self._current_job else StorageStrategy.DATED,
            base_path=str(self.get_job_path(job_id)),
            artifacts={
                "structured_md": "structured.md",
                "tables": [],
                "images": [],
                "metadata": "metadata.json",
            },
        )

        # Create content stats
        content = ParseContent(
            text_length=len(kreuzberg_result.content),
            num_tables=len(tables),
            num_images=0,  # TODO: Extract images
            num_pages=page_count,
            languages=["en"],  # TODO: Detect language
        )

        # Create result
        result = ParseResult(
            file_name=file_path.name,
            file_type="application/pdf",
            file_size_bytes=file_path.stat().st_size,
            parse_duration_ms=0,  # Will be set by base class
            storage=storage,
            content=content,
            quality=overall_quality,
            warnings=[],
        )

        # Store Kreuzberg result and tables for reference (private attributes)
        result._kreuzberg_result = kreuzberg_result  # type: ignore
        result._tables = tables  # type: ignore

        return result

    def _assess_table_quality(self, table_data: dict) -> tuple[list[QualityFlag], float]:
        """Assess table extraction quality (carrier pattern).

        Args:
            table_data: Table data from Kreuzberg

        Returns:
            Tuple of (quality_flags, confidence_score)
        """
        flags: list[QualityFlag] = []
        confidence = 1.0

        # Check for complex table structure
        if "df" in table_data:
            df = table_data["df"]
            if hasattr(df, "columns") and len(df.columns) > 10:
                flags.append(QualityFlag.COMPLEX_TABLE)
                confidence -= 0.15

        # Check for OCR usage
        if table_data.get("ocr_used", False):
            ocr_conf = table_data.get("ocr_confidence", 1.0)
            if ocr_conf < 0.8:
                flags.append(QualityFlag.LOW_OCR_CONFIDENCE)
                confidence -= 0.2

        # TODO: Add more heuristics
        # - Multi-column layout detection
        # - Missing structure detection
        # - Data loss detection

        return flags, max(0.0, confidence)

    def _assess_overall_quality(self, tables: list[ParsedTable]) -> ParseQuality:
        """Assess overall document quality.

        Args:
            tables: Parsed tables

        Returns:
            ParseQuality with overall score and flags
        """
        # Calculate average table confidence
        if tables:
            avg_confidence = sum(t.confidence for t in tables) / len(tables)
        else:
            avg_confidence = 1.0

        # Collect quality flags
        quality_flags: list[dict] = []
        for table in tables:
            if table.flags:
                for flag_str in table.flags:
                    quality_flags.append(
                        {
                            "type": flag_str,
                            "location": f"page {table.page_number}, table {table.id}",
                            "confidence": table.confidence,
                            "suggestion": (
                                "Verify with visual OCR"
                                if flag_str
                                in [
                                    QualityFlag.COMPLEX_TABLE.value,
                                    QualityFlag.LOW_OCR_CONFIDENCE.value,
                                ]
                                else "Review manually"
                            ),
                        }
                    )

        return ParseQuality(overall_score=avg_confidence, flags=quality_flags)

    async def _store_artifacts(
        self,
        result: ParseResult,
        job_id: UUID,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> None:
        """Store parse artifacts to filesystem.

        Args:
            result: Parse result
            job_id: Job ID
            progress_callback: Optional progress callback
        """
        # Get Kreuzberg result
        kreuzberg_result = result._kreuzberg_result  # type: ignore

        # Write structured content (markdown)
        md_path = self.write_artifact(job_id, "structured.md", kreuzberg_result.content)
        logger.debug(f"Wrote structured.md: {md_path}")

        # Write metadata
        metadata = {
            "provider": self.provider_name,
            "file_name": result.file_name,
            "file_type": result.file_type,
            "page_count": result.content.num_pages,
            "table_count": result.content.num_tables,
            "quality_score": result.quality.overall_score,
            "metadata": kreuzberg_result.metadata,
        }
        metadata_path = self.write_artifact(
            job_id, "metadata.json", json.dumps(metadata, indent=2)
        )
        logger.debug(f"Wrote metadata.json: {metadata_path}")

        # Write tables if any
        table_paths: list[str] = []
        tables = getattr(result, "_tables", [])  # Get private _tables attribute
        for i, table in enumerate(tables):
            table_path = f"tables/table_{i}.md"
            self.write_artifact(job_id, table_path, table.text)
            table_paths.append(table_path)

        # Update storage artifacts
        result.storage.artifacts["tables"] = table_paths

        logger.debug(f"Stored {len(table_paths)} tables for job {job_id}")
