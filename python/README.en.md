# Tibero MCP Server (Python)

An MCP (Model Context Protocol) server for Tibero DBMS. Implemented in Python.

## Key Features

This MCP server provides the following tools:

### 1. **execute_query** - SELECT Query Execution
- Execute SELECT queries and return results as JSON arrays
- Support for parameterized queries
- Return all rows as dictionaries

### 2. **execute_dml** - DML Statement Execution
- Execute INSERT, UPDATE, DELETE statements
- Automatic transaction management (commit on success, rollback on failure)
- Return number of affected rows

### 3. **get_schema** - Schema Information Retrieval
- Retrieve list of all tables and views in the database
- Include comments for each table/view
- Filter by specific schema
- Include metadata such as tablespace, row count, last analyzed date

### 4. **get_table_info** - Table/View Detailed Information
- Retrieve detailed information for a specific table or view
- **Column Information**: name, data type, length, precision, NULL allowed, default value, **column comment**
- **Constraints**: constraint name, type, status, etc.
- **Indexes**: index name, type, uniqueness, status, etc.
- Support for both tables and views (constraints/indexes are usually empty arrays for views)

### 5. **explain_plan** - Execution Plan Retrieval
- Analyze SQL query execution plan without actually executing
- Validate whether SQL is executable
- Return detailed execution plan information (using DBMS_XPLAN.DISPLAY or PLAN_TABLE)
- Return error message if SQL is invalid

### 6. **sample_table** - Table Sampling
- Sample n rows from a specific table
- Query only necessary rows without loading all data
- Default: 10 rows, Maximum: 1000 rows
- Useful for quickly checking table structure and data

## Requirements

- Python 3.12 or higher
- Java JDK 8 or higher (for JDBC driver execution)
- Tibero DBMS
- Tibero JDBC driver (tbjdbc8*.jar)

## Installation

### 1. Clone Repository

```bash
git clone <repository-url>
cd tibero-mcp/python
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Prepare JDBC Driver

Place the Tibero JDBC driver in the `lib/` directory:

- File: `lib/tbjdbc8-7.2.4.jar` (or file matching `tbjdbc8*.jar` pattern)
- JDBC driver can be found in the Tibero installation directory

### 4. Configure Environment Variables

Copy `mcp.cfg.example` to create `mcp.cfg` and enter database connection information:

```bash
# Windows
copy mcp.cfg.example mcp.cfg

# Linux/Mac
cp mcp.cfg.example mcp.cfg
```

Edit the `mcp.cfg` file to set Tibero database connection information:

```ini
# Tibero Database Connection
TIBERO_HOST=your_host
TIBERO_PORT=8629
TIBERO_DATABASE=your_database
TIBERO_USER=your_username
TIBERO_PASSWORD=your_password

# MCP Server Configuration
MCP_TRANSPORT=http          # http (default) or stdio
MCP_SERVER_HOST=0.0.0.0     # 0.0.0.0: all interfaces, localhost: local only
MCP_SERVER_PORT=8000        # HTTP server port
LOG_LEVEL=INFO
```

## Execution

```bash
python -m src.main
```

The server runs in two ways depending on the `MCP_TRANSPORT` setting in `mcp.cfg` (default: http):

### 1. HTTP Server Mode (Default)

If the setting is omitted or `MCP_TRANSPORT=http`, it runs as an HTTP server.

**Features:**
- Accessible from remote clients
- Multiple clients can connect simultaneously
- Communication over network

**Startup Message:**
```
Starting Tibero MCP Server as Streamable HTTP server on 0.0.0.0:8000
Server will be accessible at: http://0.0.0.0:8000
MCP endpoint: http://0.0.0.0:8000/mcp
```

### 2. stdio Server Mode

If `MCP_TRANSPORT=stdio` is set, it runs as a stdio server.

**Startup Message:**
```
Starting Tibero MCP Server as stdio server
Server will communicate via stdin/stdout
```

**Server Shutdown:**
- Press `Ctrl + C` in the terminal to stop the server.

## Cursor Connection Configuration

### HTTP Server Mode Connection

To connect to a remote HTTP server, configure the `~/.cursor/mcp.json` file as follows:

```json
{
  "mcpServers": {
    "tibero": {
      "url": "http://your-server-ip:8000/mcp"
    }
  }
}
```

**Local Server Connection:**
```json
{
  "mcpServers": {
    "tibero": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

### stdio Server Mode Connection

To connect to a local stdio server, configure the `~/.cursor/mcp.json` file as follows:

```json
{
  "mcpServers": {
    "tibero": {
      "command": "python",
      "args": ["-m", "src.main"],
      "cwd": "/path/to/tibero-mcp/python"
    }
  }
}
```

After configuration, restart Cursor to use the MCP tools.

## Project Structure

```
python/
├── src/
│   ├── db/                      # Database module
│   │   ├── __init__.py
│   │   ├── connector.py         # JDBC connection management
│   │   ├── query_executor.py    # Query execution and execution plan
│   │   └── schema_viewer.py     # Schema information retrieval
│   ├── mcp/                     # MCP server
│   │   ├── __init__.py
│   │   └── server.py            # FastMCP server and tool definitions
│   └── main.py                  # Entry point
├── lib/                         # JDBC driver
│   └── tbjdbc8-7.2.4.jar
├── mcp.cfg.example              # Configuration file example
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

## Troubleshooting

### Connection Errors

- Verify that Tibero database is running
- Verify that connection information in `mcp.cfg` is correct
- Check firewall settings (for HTTP server mode)

### JDBC Driver Errors

- Verify that `tbjdbc8*.jar` file exists in the `lib/` directory
- Verify that Java JDK is installed and `JAVA_HOME` is set

### Permission Errors

- Verify that the database user has necessary permissions
- Access permissions to system views such as `ALL_TABLES`, `ALL_VIEWS`, `ALL_TAB_COLUMNS` are required
