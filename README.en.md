# Tibero MCP Server

This is an MCP (Model Context Protocol) server project for Tibero DBMS. It provides two implementations: Python and Java.

## Project Structure

This project is structured as a multi-module project, where each module is an independent project:

```
tibero-mcp/
├── python/                    # Python MCP server project
│   ├── src/                   # Python source code
│   ├── lib/                   # JDBC driver
│   ├── mcp.cfg                # Configuration file
│   ├── requirements.txt       # Python dependencies
│   └── README.md              # Python project documentation
├── java/                      # Java MCP server project
│   ├── src/                   # Java source code
│   ├── build.gradle           # Gradle build configuration
│   └── README.md              # Java project documentation
└── README.md                  # This file (overall project overview)
```

## Modules

### Python Module

A Tibero MCP server implemented in Python.

**Key Features:**
- SELECT query execution
- DML statement execution (INSERT, UPDATE, DELETE)
- Schema information retrieval
- Table/view detailed information retrieval
- Execution plan retrieval
- Table sampling

**Documentation:** [python/README.md](python/README.md)

### Java Module

A Tibero MCP server implemented in Java Spring Boot. Provides the same features as the Python version.

**Key Features:**
- SELECT query execution
- DML statement execution (INSERT, UPDATE, DELETE)
- Schema information retrieval
- Table/view detailed information retrieval
- Execution plan retrieval
- Table sampling

**Documentation:** [java/README.md](java/README.md)

## Getting Started

Each module is an independent project, so navigate to the directory of the module you want to use and refer to that module's README:

- **Using Python Module:** `cd python` then refer to [python/README.md](python/README.md)
- **Using Java Module:** `cd java` then refer to [java/README.md](java/README.md)
