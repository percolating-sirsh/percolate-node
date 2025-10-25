"""Integration test for parse_document MCP tool.

Tests that percolate API can submit parse jobs to percolate-reading API.
"""

import asyncio
import sys
from pathlib import Path

# Add percolate to path
sys.path.insert(0, str(Path(__file__).parent / "percolate" / "src"))

from percolate.mcp.tools.parse import parse_document


async def test_parse_wav():
    """Test parsing WAV file via MCP tool."""
    # Create test file
    test_file = Path("/tmp/test_integration.txt")
    test_file.write_text("Integration test file for percolate parse_document MCP tool")

    print("Testing parse_document MCP tool...")
    print(f"Test file: {test_file}")
    print(f"File exists: {test_file.exists()}")

    try:
        # Call MCP tool (will make HTTP request to percolate-reading)
        result = await parse_document(
            file_path=str(test_file),
            tenant_id="test-tenant",
            storage_strategy="tenant",
        )

        print("\n✓ Parse job submitted successfully!")
        print(f"Job ID: {result.get('job_id')}")
        print(f"Status: {result.get('status')}")
        print(f"Duration: {result.get('result', {}).get('parse_duration_ms')}ms")
        print(f"Storage: {result.get('result', {}).get('storage', {}).get('base_path')}")

        # Check result structure
        assert result.get("status") == "completed", f"Expected status=completed, got {result.get('status')}"
        assert result.get("job_id"), "Missing job_id"
        assert result.get("result"), "Missing result"

        print("\n✅ Integration test passed!")
        return True

    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_parse_wav())
    sys.exit(0 if success else 1)
