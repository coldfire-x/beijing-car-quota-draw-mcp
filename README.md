# Beijing Car Quota Lottery MCP Server

An MCP (Model Context Protocol) server that provides AI agents with the ability to query Beijing car quota lottery results. This server scrapes data from the Beijing Transportation Commission website and exposes search capabilities through a standardized MCP interface.

## Features

- **🔍 Smart Search**: Search by application code (申请编码) or partial ID number
- **📄 PDF Processing**: Automatically parses different PDF formats (waiting lists and score rankings)
- **🌐 Web Scraping**: Scrapes latest data from Beijing Transportation Commission website
- **🤖 AI Integration**: Exposes functionality as MCP tools for AI agents like Claude, Cursor, etc.
- **💾 Data Persistence**: Stores processed data locally with fast indexing
- **📊 Statistics**: Provides insights into loaded data and search results

## Tech Stack

- **Language**: Python 3.9+
- **Web Framework**: FastAPI
- **MCP Framework**: fastapi-mcp
- **PDF Processing**: pdfplumber
- **Web Scraping**: crawl4ai
- **Dependency Management**: uv

## Installation

### Prerequisites

- Python 3.9 or higher
- uv (recommended) or pip

### Using uv (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd bjhjyd-mcp

# Install dependencies
uv sync

# Activate virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### Using pip

```bash
# Clone the repository
git clone <repository-url>
cd bjhjyd-mcp

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .
```

## Quick Start

### 1. Start the MCP Server

```bash
# Using the main module
python -m bjhjyd_mcp.main

# Or with custom settings
python -m bjhjyd_mcp.main --host 0.0.0.0 --port 8080 --log-level DEBUG
```

The server will start at `http://127.0.0.1:8000` by default.

### 2. Access the API

- **API Documentation**: http://127.0.0.1:8000/docs
- **MCP Endpoint**: http://127.0.0.1:8000/mcp
- **Health Check**: http://127.0.0.1:8000/health

### 3. Configure AI Clients

#### For Cursor IDE

1. Go to Settings → MCP → Add new MCP server
2. Add this configuration:

```json
{
  "mcpServers": {
    "Beijing Car Quota": {
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

#### For Claude Desktop

1. Install mcp-proxy: `uv tool install mcp-proxy`
2. Configure in `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "Beijing Car Quota": {
      "command": "mcp-proxy",
      "args": ["http://127.0.0.1:8000/mcp"]
    }
  }
}
```

## Available MCP Tools

The server exposes the following tools for AI agents:

### 1. `search_by_application_code`
Search for quota results by application code (申请编码).

**Parameters:**
- `application_code` (string): The application code to search for

**Example:**
```json
{
  "application_code": "1437100439239"
}
```

### 2. `search_by_id_number`
Search for quota results by partial ID number (first 6 and last 4 digits).

**Parameters:**
- `id_prefix` (string): First 6 digits of ID number
- `id_suffix` (string): Last 4 digits of ID number

**Example:**
```json
{
  "id_prefix": "110228",
  "id_suffix": "1240"
}
```

### 3. `get_data_statistics`
Get statistics about loaded quota data.

**Returns:** Information about total files, entries, and data breakdown.

### 4. `refresh_data`
Refresh quota data by scraping the latest PDFs from the website.

**Parameters:**
- `max_pages` (integer, optional): Maximum pages to scrape (default: 5)

### 5. `list_data_files`
List all loaded quota data files with metadata.

### 6. `health_check`
Check server health and status.

## Data Formats

The server handles two types of PDF formats from the Beijing Transportation Commission:

### 1. Waiting List (轮候序号列表)
- **Fields**: 序号, 申请编码, 轮候时间
- **Purpose**: Time-based ordering for quota applications

### 2. Score Ranking (积分排序入围名单)
- **Fields**: 序号, 申请编码, 姓名, 身份证号, 家庭代际数, 积分, 注册时间
- **Purpose**: Score-based ranking with personal information
- **Privacy**: ID numbers are masked (e.g., 110228\*\*\*\*\*\*\*\*1240)

## Development

### Project Structure

```
src/
├── bjhjyd_mcp/
│   ├── __init__.py
│   ├── main.py              # Entry point
│   ├── models/              # Data models
│   │   ├── quota_result.py
│   ├── parsers/             # PDF parsing
│   │   ├── pdf_parser.py
│   ├── scrapers/            # Web scraping
│   │   ├── web_scraper.py
│   ├── server/              # MCP server
│   │   ├── mcp_server.py
│   ├── storage/             # Data storage
│   │   ├── data_store.py
│   └── utils/               # Utilities
│       ├── logging_config.py
└── tests/
    ├── unit/
    └── integration/
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest src/tests/unit/test_pdf_parser.py
```

### Code Quality

```bash
# Format code
black src/

# Sort imports
isort src/

# Type checking
mypy src/

# Linting
flake8 src/
```

## Configuration

### Environment Variables

- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `DATA_DIR`: Directory for storing processed data
- `DOWNLOADS_DIR`: Directory for downloaded PDF files

### Command Line Options

```bash
python -m bjhjyd_mcp.main --help
```

## API Examples

### Direct API Usage

```python
import httpx

# Search by application code
response = httpx.post(
    "http://127.0.0.1:8000/search/application-code",
    json={"application_code": "1437100439239"}
)
print(response.json())

# Get statistics
response = httpx.get("http://127.0.0.1:8000/data/statistics")
print(response.json())
```

### Using with AI Agents

Once configured, AI agents can use natural language to query the data:

- "Check if application code 1437100439239 won the lottery"
- "Search for ID number starting with 110228 and ending with 1240"
- "Show me the latest quota lottery statistics"
- "Refresh the data with new PDFs from the website"

## Troubleshooting

### Common Issues

1. **Server won't start**
   - Check if port 8000 is available
   - Verify all dependencies are installed
   - Check logs for specific error messages

2. **No data found**
   - Run `refresh_data` tool to scrape latest PDFs
   - Check if example PDFs exist in the `examples/` directory
   - Verify network connectivity for web scraping

3. **PDF parsing errors**
   - Check PDF format compatibility
   - Verify PDF files are not corrupted
   - Review parsing logs for specific issues

### Logging

Enable debug logging for detailed information:

```bash
python -m bjhjyd_mcp.main --log-level DEBUG --log-file logs/server.log
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This tool is for educational and research purposes only. Please respect the Beijing Transportation Commission's terms of service and rate limits when scraping their website. 