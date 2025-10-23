"""HTTP client for percolate-reading API."""

from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel


class ParseResult(BaseModel):
    """Result from document parsing."""

    content: str
    metadata: dict[str, Any]
    tables: list[dict[str, Any]] = []
    images: list[str] = []
    quality_flags: list[str] = []


class EmbeddingResult(BaseModel):
    """Result from embedding generation."""

    embeddings: list[list[float]]
    model: str


class OCRResult(BaseModel):
    """Result from OCR extraction."""

    text: str
    confidence: float
    language: str


class ReadingClient:
    """Client for percolate-reading API.

    This client communicates with the reading node (percolate-reading)
    for heavy processing operations like document parsing, embeddings,
    OCR, and transcription.

    Args:
        base_url: Base URL of reading node API (e.g., "http://localhost:8001")
        timeout: Request timeout in seconds (default: 30)
    """

    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=timeout)

    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()

    async def __aenter__(self) -> "ReadingClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def parse_pdf(
        self,
        file_path: Path,
        tenant_id: str,
        extract_tables: bool = True,
        ocr_fallback: bool = True,
    ) -> ParseResult:
        """Parse PDF document.

        Args:
            file_path: Path to PDF file
            tenant_id: Tenant ID for isolation
            extract_tables: Extract tables from PDF
            ocr_fallback: Use OCR for scanned pages

        Returns:
            ParseResult with content, tables, and quality flags
        """
        with open(file_path, "rb") as f:
            response = await self.client.post(
                f"{self.base_url}/parse/pdf",
                files={"file": f},
                data={
                    "tenant_id": tenant_id,
                    "extract_tables": extract_tables,
                    "ocr_fallback": ocr_fallback,
                },
            )
        response.raise_for_status()
        return ParseResult(**response.json())

    async def parse_excel(self, file_path: Path, tenant_id: str) -> ParseResult:
        """Parse Excel workbook.

        Args:
            file_path: Path to Excel file
            tenant_id: Tenant ID for isolation

        Returns:
            ParseResult with content and metadata
        """
        with open(file_path, "rb") as f:
            response = await self.client.post(
                f"{self.base_url}/parse/excel",
                files={"file": f},
                data={"tenant_id": tenant_id},
            )
        response.raise_for_status()
        return ParseResult(**response.json())

    async def parse_audio(
        self,
        file_path: Path,
        tenant_id: str,
        language: str = "en",
        diarization: bool = True,
    ) -> ParseResult:
        """Transcribe audio file.

        Args:
            file_path: Path to audio file
            tenant_id: Tenant ID for isolation
            language: Language code (e.g., "en", "es")
            diarization: Enable speaker diarization

        Returns:
            ParseResult with transcript and speaker labels
        """
        with open(file_path, "rb") as f:
            response = await self.client.post(
                f"{self.base_url}/parse/audio",
                files={"file": f},
                data={
                    "tenant_id": tenant_id,
                    "language": language,
                    "diarization": diarization,
                },
            )
        response.raise_for_status()
        return ParseResult(**response.json())

    async def embed_batch(
        self,
        texts: list[str],
        tenant_id: str,
        model: str = "nomic-embed-text-v1.5",
    ) -> EmbeddingResult:
        """Generate embeddings for text batch.

        Args:
            texts: List of texts to embed
            tenant_id: Tenant ID for isolation
            model: Embedding model name

        Returns:
            EmbeddingResult with embeddings and model info
        """
        response = await self.client.post(
            f"{self.base_url}/embed/batch",
            json={"texts": texts, "tenant_id": tenant_id, "model": model},
        )
        response.raise_for_status()
        return EmbeddingResult(**response.json())

    async def ocr_extract(
        self,
        image_path: Path,
        tenant_id: str,
        language: str = "eng",
    ) -> OCRResult:
        """Extract text from image using OCR.

        Args:
            image_path: Path to image file
            tenant_id: Tenant ID for isolation
            language: OCR language (e.g., "eng", "spa")

        Returns:
            OCRResult with extracted text and confidence
        """
        with open(image_path, "rb") as f:
            response = await self.client.post(
                f"{self.base_url}/ocr/extract",
                files={"image": f},
                data={"tenant_id": tenant_id, "language": language},
            )
        response.raise_for_status()
        return OCRResult(**response.json())

    async def health_check(self) -> dict[str, Any]:
        """Check reading node health.

        Returns:
            Health status and metrics
        """
        response = await self.client.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()
