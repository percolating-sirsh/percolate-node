"""Image OCR using pytesseract for text extraction.

Based on carrier patterns with local Tesseract OCR.
Simple text extraction without layout analysis.
"""

import json
from pathlib import Path
from typing import Callable
from uuid import UUID

import pytesseract
from loguru import logger
from PIL import Image

from percolate_reading.models.parse import (
    ParseContent,
    ParseQuality,
    ParseResult,
    ParseStorage,
    StorageStrategy,
)
from percolate_reading.providers.base import ParseProvider
from percolate_reading.storage.manager import StorageManager


class ImageProvider(ParseProvider):
    """Image OCR provider using pytesseract.

    Features:
    - Text extraction from images
    - Language detection
    - Confidence scoring
    - Simple layout preservation

    Performance:
    - ~500ms per image (CPU)
    - Quality depends on image resolution
    """

    def __init__(self, storage_manager: StorageManager):
        """Initialize Image provider.

        Args:
            storage_manager: Storage manager for artifacts
        """
        super().__init__(storage_manager)

    @property
    def supported_types(self) -> list[str]:
        """Supported MIME types."""
        return [
            "image/png",
            "image/jpeg",
            "image/jpg",
            "image/tiff",
            "image/bmp",
            "image/webp",
        ]

    @property
    def provider_name(self) -> str:
        """Provider name."""
        return "tesseract_ocr"

    async def _parse(
        self,
        file_path: Path,
        job_id: UUID,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> ParseResult:
        """Extract text from image using Tesseract OCR.

        Args:
            file_path: Path to image file
            job_id: Job ID for artifact storage
            progress_callback: Optional progress callback

        Returns:
            ParseResult with extracted text and metadata

        Raises:
            Exception: On OCR failure
        """
        if progress_callback:
            progress_callback(0.1, "Loading image")

        # Load image
        try:
            image = Image.open(file_path)
        except Exception as e:
            raise Exception(f"Failed to load image: {e}")

        if progress_callback:
            progress_callback(0.3, "Running OCR")

        # Perform OCR
        try:
            # Get detailed data with confidence scores
            ocr_data = pytesseract.image_to_data(
                image,
                output_type=pytesseract.Output.DICT,
                lang="eng",  # TODO: Auto-detect language
            )

            # Extract text with simple formatting
            text = pytesseract.image_to_string(image, lang="eng")

            # Calculate average confidence
            confidences = [
                int(conf) for conf in ocr_data["conf"] if int(conf) >= 0
            ]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0

            logger.info(
                f"OCR extracted {len(text)} characters "
                f"(avg confidence: {avg_confidence:.1f}%)"
            )

        except Exception as e:
            raise Exception(f"OCR failed: {e}")
        finally:
            image.close()

        if progress_callback:
            progress_callback(0.7, "Building parse result")

        # Create storage info
        storage = ParseStorage(
            strategy=self._current_job.storage_strategy if self._current_job else StorageStrategy.DATED,
            base_path=str(self.get_job_path(job_id)),
            artifacts={
                "text": "extracted_text.txt",
                "ocr_data": "ocr_data.json",
                "metadata": "metadata.json",
            },
        )

        # Create content stats
        content = ParseContent(
            text_length=len(text),
            num_tables=0,
            num_images=1,
            num_pages=1,
            languages=["en"],  # TODO: Detect from OCR
        )

        # Quality assessment based on OCR confidence
        quality_score = avg_confidence / 100.0
        quality = ParseQuality(
            overall_score=quality_score,
            flags=(
                [{
                    "type": "LOW_OCR_CONFIDENCE",
                    "location": "overall",
                    "confidence": quality_score,
                    "suggestion": "Verify with higher resolution image",
                }]
                if quality_score < 0.8
                else []
            ),
        )

        # Create result
        result = ParseResult(
            file_name=file_path.name,
            file_type="image/png",  # Generic
            file_size_bytes=file_path.stat().st_size,
            parse_duration_ms=0,  # Will be set by base provider
            storage=storage,
            content=content,
            quality=quality,
            warnings=(
                ["Low OCR confidence - text may be inaccurate"]
                if quality_score < 0.8
                else []
            ),
        )

        # Store OCR data
        result._text = text  # type: ignore
        result._ocr_data = {
            "average_confidence": avg_confidence,
            "word_count": len([w for w in ocr_data["text"] if w.strip()]),
            "image_dimensions": {"width": image.width, "height": image.height},
        }  # type: ignore

        if progress_callback:
            progress_callback(0.9, "Writing artifacts")

        # Store artifacts
        await self._store_artifacts(result, job_id, progress_callback)

        if progress_callback:
            progress_callback(1.0, "OCR complete")

        return result

    async def _store_artifacts(
        self,
        result: ParseResult,
        job_id: UUID,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> None:
        """Store OCR artifacts.

        Args:
            result: ParseResult with OCR data
            job_id: Job ID for storage path
            progress_callback: Optional progress callback
        """
        # Get data from private attributes
        text = getattr(result, "_text", "")
        ocr_data = getattr(result, "_ocr_data", {})

        # Write extracted text
        text_path = self.write_artifact(job_id, "extracted_text.txt", text)
        logger.debug(f"Wrote extracted_text.txt: {text_path}")

        # Write OCR data
        ocr_path = self.write_artifact(
            job_id, "ocr_data.json", json.dumps(ocr_data, indent=2)
        )
        logger.debug(f"Wrote ocr_data.json: {ocr_path}")

        # Write metadata
        metadata = {
            "file_name": result.file_name,
            "file_size_bytes": result.file_size_bytes,
            "ocr_info": ocr_data,
        }
        metadata_path = self.write_artifact(
            job_id, "metadata.json", json.dumps(metadata, indent=2)
        )
        logger.debug(f"Wrote metadata.json: {metadata_path}")
