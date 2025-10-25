"""Test PDF parsing with Kreuzberg provider."""

import pytest
from pathlib import Path
from uuid import uuid4

from percolate_reading.models.parse import (
    ParseJob,
    ParseStatus,
    StorageStrategy,
)
from percolate_reading.providers.pdf import PDFProvider
from percolate_reading.storage.manager import StorageManager


@pytest.fixture
def storage_manager(tmp_path):
    """Create storage manager with temp directory."""
    return StorageManager(
        base_path=tmp_path / "parse-jobs",
        default_strategy=StorageStrategy.DATED,
    )


@pytest.fixture
def pdf_provider(storage_manager):
    """Create PDF provider."""
    return PDFProvider(storage_manager)


@pytest.mark.asyncio
async def test_pdf_parsing_basic(pdf_provider, tmp_path):
    """Test basic PDF parsing with Kreuzberg.

    This test requires a sample PDF file. For now, we'll skip if file doesn't exist.
    """
    # Create a simple test PDF (would need reportlab or similar)
    # For now, skip if no test file available
    test_pdf = Path(__file__).parent / "fixtures" / "test.pdf"

    if not test_pdf.exists():
        pytest.skip("Test PDF not available - create tests/fixtures/test.pdf")

    # Create job
    job = ParseJob(
        job_id=uuid4(),
        file_name="test.pdf",
        file_type="application/pdf",
        status=ParseStatus.PROCESSING,
        storage_strategy=StorageStrategy.DATED,
    )

    # Parse
    result = await pdf_provider.parse(test_pdf, job)

    # Verify result
    assert result.file_name == "test.pdf"
    assert result.file_type == "application/pdf"
    assert result.parse_duration_ms > 0
    assert result.content.num_pages >= 0
    assert result.quality.overall_score >= 0.0
    assert result.quality.overall_score <= 1.0


@pytest.mark.asyncio
async def test_pdf_provider_supported_types(pdf_provider):
    """Test that PDF provider supports correct MIME types."""
    assert "application/pdf" in pdf_provider.supported_types
    assert pdf_provider.provider_name == "kreuzberg_pdf"


@pytest.mark.asyncio
async def test_pdf_parsing_with_progress(pdf_provider, tmp_path):
    """Test PDF parsing with progress callback."""
    test_pdf = Path(__file__).parent / "fixtures" / "test.pdf"

    if not test_pdf.exists():
        pytest.skip("Test PDF not available")

    # Track progress updates
    progress_updates = []

    def progress_callback(progress: float, message: str):
        progress_updates.append((progress, message))

    # Create job
    job = ParseJob(
        job_id=uuid4(),
        file_name="test.pdf",
        file_type="application/pdf",
        status=ParseStatus.PROCESSING,
        storage_strategy=StorageStrategy.DATED,
    )

    # Parse with progress callback
    result = await pdf_provider.parse(test_pdf, job, progress_callback)

    # Verify progress updates were called
    assert len(progress_updates) > 0
    assert progress_updates[-1][0] == 1.0  # Final progress should be 100%
    assert "complete" in progress_updates[-1][1].lower()


def test_pdf_provider_registry_integration(storage_manager):
    """Test that PDF provider can be registered and retrieved."""
    from percolate_reading.providers.base import ProviderRegistry

    registry = ProviderRegistry(storage_manager)
    pdf_provider = PDFProvider(storage_manager)

    # Register
    registry.register(pdf_provider)

    # Retrieve
    provider = registry.get_provider("application/pdf")
    assert provider.provider_name == "kreuzberg_pdf"

    # List supported types
    assert "application/pdf" in registry.list_supported_types()
