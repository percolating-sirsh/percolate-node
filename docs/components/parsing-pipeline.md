# Document Parsing Pipeline Component Design

## Responsibility

Fast, accurate document parsing (PDF, Excel, Audio, Office) with structured extraction and quality verification.

## Strategy

**Two-tier approach:**
1. **Fast path (Rust)**: Semantic extraction, structure detection
2. **Verification path (Python + LLM)**: Quality validation, visual verification for uncertain content

## Components

### 1. PDF Parser (Rust Core)

**Implementation:**
```rust
// percolate-core/src/parsers/pdf.rs
use pdf_extract::extract_text;

pub struct PdfParser {
    config: PdfParserConfig,
}

pub struct ParseResult {
    pub content: String,
    pub tables: Vec<Table>,
    pub images: Vec<Image>,
    pub metadata: Metadata,
    pub quality_flags: Vec<QualityFlag>,
}

impl PdfParser {
    pub fn parse(&self, pdf_path: &Path) -> Result<ParseResult> {
        // 1. Extract text with position information
        let pages = extract_pages_with_layout(pdf_path)?;

        // 2. Detect tables
        let tables = detect_tables(&pages)?;

        // 3. Extract images
        let images = extract_images(pdf_path)?;

        // 4. Generate quality flags
        let quality_flags = assess_quality(&pages, &tables)?;

        // 5. Convert to markdown
        let content = to_markdown(&pages, &tables)?;

        Ok(ParseResult {
            content,
            tables,
            images,
            metadata: extract_metadata(pdf_path)?,
            quality_flags,
        })
    }
}

pub enum QualityFlag {
    LowConfidenceTable { page: usize, reason: String },
    PossibleOcr { page: usize },
    ComplexLayout { page: usize },
    MissingContent { page: usize },
}
```

**Python Binding:**
```python
from percolate_core import PdfParser, ParseResult

parser = PdfParser(config={"ocr": False, "extract_images": True})
result: ParseResult = parser.parse("document.pdf")

print(result.content)  # Markdown text
print(result.tables)   # Structured tables
print(result.quality_flags)  # Issues requiring verification
```

### 2. Excel Parser (Rust Core)

**Implementation:**
```rust
// percolate-core/src/parsers/excel.rs
use calamine::{Reader, Xlsx, open_workbook};

pub struct ExcelParser;

pub struct SheetAnalysis {
    pub name: String,
    pub structure: SheetStructure,
    pub data: Vec<Vec<Cell>>,
    pub charts: Vec<Chart>,
}

pub enum SheetStructure {
    Table { headers: Vec<String>, rows: usize },
    Matrix { dimensions: (usize, usize) },
    Dashboard { layout: Layout },
    Unknown,
}

impl ExcelParser {
    pub fn parse(&self, excel_path: &Path) -> Result<Vec<SheetAnalysis>> {
        let mut workbook: Xlsx<_> = open_workbook(excel_path)?;

        let mut sheets = Vec::new();

        for sheet_name in workbook.sheet_names() {
            let range = workbook.worksheet_range(&sheet_name)?;

            // Detect structure
            let structure = detect_structure(&range)?;

            // Extract data
            let data = extract_cells(&range)?;

            sheets.push(SheetAnalysis {
                name: sheet_name.clone(),
                structure,
                data,
                charts: extract_charts(&sheet_name)?,
            });
        }

        Ok(sheets)
    }
}
```

### 3. Audio Parser (Python + Whisper)

**Implementation:**
```python
# percolate/parsers/audio.py
from faster_whisper import WhisperModel

class AudioParser:
    def __init__(self, model_size: str = "base"):
        self.model = WhisperModel(model_size, device="cpu", compute_type="int8")

    def parse(self, audio_path: Path) -> ParseResult:
        # Transcribe with timestamps
        segments, info = self.model.transcribe(
            str(audio_path),
            beam_size=5,
            word_timestamps=True
        )

        transcript = []
        for segment in segments:
            transcript.append({
                "start": segment.start,
                "end": segment.end,
                "text": segment.text,
                "words": [
                    {"word": w.word, "start": w.start, "end": w.end}
                    for w in segment.words
                ]
            })

        # Detect speakers (simple heuristic)
        speakers = self.detect_speakers(transcript)

        return ParseResult(
            content=self.to_markdown(transcript, speakers),
            metadata={"language": info.language, "duration": info.duration},
            artifacts={"transcript": transcript, "speakers": speakers}
        )
```

### 4. Orchestration Layer (Python)

**Parse Job Management:**
```python
# percolate/parsers/job.py
from enum import Enum
from pydantic import BaseModel

class ParseStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_VERIFICATION = "needs_verification"

class ParseJob(BaseModel):
    id: str
    tenant_id: str
    file_path: str
    file_type: str
    status: ParseStatus
    result: Optional[ParseResult] = None
    error: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

async def create_parse_job(file_path: Path, tenant_id: str) -> ParseJob:
    job = ParseJob(
        id=uuid4(),
        tenant_id=tenant_id,
        file_path=str(file_path),
        file_type=detect_file_type(file_path),
        status=ParseStatus.PENDING,
        created_at=datetime.now()
    )

    await db.execute("INSERT INTO parse_jobs (...) VALUES (...)")

    # Enqueue for processing
    await queue.enqueue("parse_document", job.id)

    return job
```

**Parser Dispatcher:**
```python
# percolate/parsers/dispatcher.py
async def parse_document(job_id: str):
    job = await load_job(job_id)

    try:
        # Update status
        await update_job_status(job_id, ParseStatus.PROCESSING)

        # Select parser
        parser = get_parser(job.file_type)

        # Parse (Rust)
        result = parser.parse(Path(job.file_path))

        # Check quality flags
        if result.quality_flags:
            await update_job_status(job_id, ParseStatus.NEEDS_VERIFICATION)
            await schedule_verification(job_id, result.quality_flags)
        else:
            await finalize_job(job_id, result)

    except Exception as e:
        await update_job_status(job_id, ParseStatus.FAILED, error=str(e))

def get_parser(file_type: str) -> Parser:
    parsers = {
        "pdf": PdfParser(),
        "xlsx": ExcelParser(),
        "mp3": AudioParser(),
        "wav": AudioParser(),
    }
    return parsers[file_type]
```

### 5. Quality Verification (Python + LLM)

**Visual Verification for PDFs:**
```python
# percolate/parsers/verify.py
from anthropic import Anthropic

async def verify_quality_flags(job_id: str, flags: list[QualityFlag]):
    job = await load_job(job_id)

    for flag in flags:
        if isinstance(flag, LowConfidenceTable):
            # Use LLM vision to verify table
            verified_table = await verify_table_with_vision(
                pdf_path=job.file_path,
                page=flag.page,
                table_bbox=flag.bbox
            )

            # Update result with verified table
            await update_parse_result(job_id, verified_table)

    # Mark as completed
    await update_job_status(job_id, ParseStatus.COMPLETED)

async def verify_table_with_vision(pdf_path: Path, page: int, table_bbox: BBox) -> Table:
    # Render PDF page as image
    image = render_pdf_page(pdf_path, page)

    # Crop to table region
    table_image = crop_image(image, table_bbox)

    # Ask LLM to extract table
    client = Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4.5",
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "data": encode_image(table_image)}},
                {"type": "text", "text": "Extract this table as structured JSON."}
            ]
        }]
    )

    return parse_table_json(response.content)
```

## Pipeline Flow

```
User uploads file
  ↓
Create ParseJob (PENDING)
  ↓
Enqueue for processing
  ↓
Worker picks up job (PROCESSING)
  ↓
Select parser by file type
  ↓
Fast extraction (Rust)
  ├─ Success, no quality flags
  │   ↓
  │   Finalize job (COMPLETED)
  │   ↓
  │   Store in REM memory
  │
  └─ Quality flags present
      ↓
      Mark NEEDS_VERIFICATION
      ↓
      Schedule verification task
      ↓
      LLM visual verification
      ↓
      Update result (COMPLETED)
      ↓
      Store in REM memory
```

## Storage

**Parse Job Schema (PostgreSQL):**
```sql
CREATE TABLE parse_jobs (
    id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_type TEXT NOT NULL,
    status TEXT NOT NULL,
    result JSONB,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_parse_jobs_tenant_status ON parse_jobs(tenant_id, status);
CREATE INDEX idx_parse_jobs_created_at ON parse_jobs(created_at);
```

**Parsed Content Storage:**
```python
# Store in REM as resources
async def finalize_job(job_id: str, result: ParseResult):
    job = await load_job(job_id)

    # Chunk content
    chunks = chunk_content(result.content, strategy="semantic")

    # Create resources
    resource_ids = []
    for chunk in chunks:
        resource_id = await memory_engine.create_resource(
            Resource(
                content=chunk.text,
                metadata={
                    "source_uri": job.file_path,
                    "page": chunk.page,
                    "parse_job_id": job_id,
                    "file_type": job.file_type
                }
            )
        )
        resource_ids.append(resource_id)

    # Store tables as structured entities
    for table in result.tables:
        entity_id = await memory_engine.create_entity(
            Entity(
                type="table",
                name=f"Table from {Path(job.file_path).name}",
                properties={"data": table.to_dict()}
            )
        )

    # Update job with result
    await update_job_status(job_id, ParseStatus.COMPLETED)
```

## Performance

**Targets:**
- PDF (10 pages): <2 seconds (fast path)
- Excel (5 sheets): <1 second
- Audio (1 hour): <5 minutes (Whisper base model)
- Visual verification: <10 seconds per flag

**Optimization:**
- Parallel page processing for PDFs
- Streaming for large files
- Batch LLM calls for multiple quality flags
- Cache rendered PDF pages

## Testing

```python
@pytest.mark.asyncio
async def test_pdf_parsing_flow():
    # Create parse job
    job = await create_parse_job(Path("test.pdf"), "test-tenant")

    # Process
    await parse_document(job.id)

    # Verify
    job = await load_job(job.id)
    assert job.status == ParseStatus.COMPLETED
    assert job.result.content
    assert len(job.result.tables) > 0
```

## Future Enhancements

- OCR fallback for scanned PDFs (Tesseract)
- Layout analysis (LayoutLM)
- Form extraction (key-value pairs)
- Multi-modal embeddings (text + image)
- Streaming parsing for large files
