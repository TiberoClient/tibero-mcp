# Tibero MCP Server (Java)

An MCP (Model Context Protocol) server for Tibero DBMS. Implemented in Java.

## Overview

This project is a Java-based Tibero MCP server. It supports both STDIO and HTTP modes.

## Key Features

- **execute_query** - SELECT query execution
- **execute_dml** - DML statement execution (INSERT, UPDATE, DELETE)
- **get_schema** - Schema information retrieval
- **get_table_info** - Table/view detailed information
- **explain_plan** - Execution plan retrieval
- **sample_table** - Table sampling

## Requirements

- Java JDK 17 or higher
- Gradle 7.0 or higher (build tool)
- Tibero DBMS
- Tibero JDBC driver (automatically downloaded from Maven Central)

## Quick Start

### 1. Build

```bash
./gradlew clean build
```

Built JAR file: `build/libs/tibero-mcp-server-{version}.jar`

### 2. Configure Database Connection Information

Set via environment variables (recommended):

| Environment Variable | Description | Default | Required |
|---------------------|-------------|---------|----------|
| `TIBERO_HOST` | Database host | `localhost` | ❌ |
| `TIBERO_PORT` | Database port | `8629` | ❌ |
| `TIBERO_DATABASE` | Database name | `tibero` | ❌ |
| `TIBERO_USER` | Username | `tibero` | ❌ |
| `TIBERO_PASSWORD` | Password | - | ✅ |

**Configuration Example:**

```bash
# Linux/Mac
export TIBERO_HOST=localhost
export TIBERO_PORT=8629
export TIBERO_DATABASE=tibero
export TIBERO_USER=tibero
export TIBERO_PASSWORD=your_password

# Windows (PowerShell)
$env:TIBERO_HOST="localhost"
$env:TIBERO_PORT="8629"
$env:TIBERO_DATABASE="tibero"
$env:TIBERO_USER="tibero"
$env:TIBERO_PASSWORD="your_password"
```

Or set directly in `src/main/resources/application.yml`:

```yaml
spring:
  datasource:
    host: localhost
    port: 8629
    database: tibero
    username: tibero
    password: your_password
```

Or **set directly in the Cursor configuration file (`~/.cursor/mcp.json`) using the `env` field** (most convenient method):

```json
{
  "mcpServers": {
    "tibero-java": {
      "command": "java",
      "args": ["-jar", "/path/to/tibero-mcp-server-{version}.jar"],
      "env": {
        "TIBERO_HOST": "localhost",
        "TIBERO_PORT": "8629",
        "TIBERO_DATABASE": "tibero",
        "TIBERO_USER": "tibero",
        "TIBERO_PASSWORD": "your_password"
      }
    }
  }
}
```

> **Note**: 
> - If environment variables are set, environment variable values take precedence
> - Values in the Cursor configuration file's `env` field take precedence over system environment variables
> - Setting directly in the Cursor configuration file is more convenient as you don't need to set system environment variables

### 3. Select Execution Mode

This MCP server supports two execution modes:

| Mode | Description | Executor | Use Case |
|------|-------------|----------|----------|
| **STDIO** | Communication via stdin/stdout | Cursor automatically executes | Local development, single user |
| **HTTP** | Run as HTTP server | User executes directly | Remote access, multiple users |

> **Important**: 
> - **STDIO Mode**: Cursor automatically executes the process, so **you don't need to run it manually**. Just configure Cursor.
> - **HTTP Mode**: **You must run the server in advance** for Cursor to connect.

#### STDIO Mode (Default, Recommended)

Cursor automatically executes the process, so no separate execution is needed. Just configure Cursor connection.

> **Note**: To run directly for testing purposes:
> ```bash
> java -jar build/libs/tibero-mcp-server-{version}.jar
> # Or during development
> ./gradlew run
> ```

#### HTTP Mode

**You must run the server directly.**

1. Configure `src/main/resources/application.yml`:

```yaml
spring:
  main:
    web-application-type: servlet
  ai:
    mcp:
      server:
        stdio: false
        http:
          enabled: true
          protocol: STREAMABLE

server:
  port: 8080  # Default
```

2. Run the server:

```bash
# Run JAR
java -Dmcp.mode.http=true -jar build/libs/tibero-mcp-server-{version}.jar

# Or during development
./gradlew run -Dmcp.mode.http=true
```

Once the server starts, it will be accessible at `http://localhost:8080`. **You must keep this server running** for Cursor to connect.

## Cursor Connection Configuration

Add the following configuration to the `~/.cursor/mcp.json` file:

### STDIO Mode (Recommended)

**Cursor automatically executes the process.** You don't need to run the process separately.

**Linux/Mac:**

```json
{
  "mcpServers": {
    "tibero-java": {
      "command": "java",
      "args": ["-jar", "/path/to/tibero-mcp/java/build/libs/tibero-mcp-server-{version}.jar"]
    }
  }
}
```

**Windows:**

```json
{
  "mcpServers": {
    "tibero-java": {
      "command": "java",
      "args": ["-jar", "C:\\path\\to\\tibero-mcp\\java\\build\\libs\\tibero-mcp-server-{version}.jar"]
    }
  }
}
```

**Setting Environment Variables Directly in JSON (Recommended):**

You can include environment variables directly in the Cursor configuration file without setting them in the system:

**Linux/Mac:**

```json
{
  "mcpServers": {
    "tibero-java": {
      "command": "java",
      "args": ["-jar", "/path/to/tibero-mcp/java/build/libs/tibero-mcp-server-{version}.jar"],
      "env": {
        "TIBERO_HOST": "localhost",
        "TIBERO_PORT": "8629",
        "TIBERO_DATABASE": "tibero",
        "TIBERO_USER": "tibero",
        "TIBERO_PASSWORD": "your_password"
      }
    }
  }
}
```

**Windows:**

```json
{
  "mcpServers": {
    "tibero-java": {
      "command": "java",
      "args": ["-jar", "C:\\path\\to\\tibero-mcp\\java\\build\\libs\\tibero-mcp-server-{version}.jar"],
      "env": {
        "TIBERO_HOST": "localhost",
        "TIBERO_PORT": "8629",
        "TIBERO_DATABASE": "tibero",
        "TIBERO_USER": "tibero",
        "TIBERO_PASSWORD": "your_password"
      }
    }
  }
}
```

> **Note**: 
> - Replace `{version}` with the actual version number (e.g., `0.0.1`)
> - Using the `env` field eliminates the need to set system environment variables
> - Environment variables in the `env` field take precedence over system environment variables
> - After configuration, restart Cursor and it will connect automatically

### HTTP Mode

**⚠️ Warning: To connect in HTTP mode, you must run the server first.** (Refer to the "HTTP Mode" execution method above)

**Local Server:**

```json
{
  "mcpServers": {
    "tibero-java-http": {
      "url": "http://localhost:8080"
    }
  }
}
```

**Remote Server:**

```json
{
  "mcpServers": {
    "tibero-java-http": {
      "url": "http://your-server-ip:8080"
    }
  }
}
```

> **Note**: 
> - The server must be running to connect
> - Verify that the server address and port are correct
> - Check firewall settings

## Project Structure

```
java/
├── src/
│   └── main/
│       ├── java/
│       │   └── tibero/mcp/
│       │       ├── TiberoMcpServerApplication.java
│       │       ├── db/
│       │       │   ├── DataSourceConfig.java
│       │       │   └── DatabaseService.java
│       │       └── tools/
│       │           ├── ExecuteQueryTool.java
│       │           ├── ExecuteDmlTool.java
│       │           ├── GetSchemaTool.java
│       │           ├── GetTableInfoTool.java
│       │           ├── ExplainPlanTool.java
│       │           └── SampleTableTool.java
│       └── resources/
│           └── application.yml
├── build.gradle
├── settings.gradle
└── README.md
```

## Technology Stack

- **Java 17+**: Minimum required Java version
- **Spring Boot 3.5.3**: Application framework
- **Spring AI MCP Server**: MCP protocol implementation
- **Tibero JDBC Driver 7.2.4**: Tibero database connection
- **HikariCP**: Connection pool
- **Gradle**: Build tool

## Troubleshooting

### Connection Errors

- Verify that Tibero database is running
- Verify that connection information in environment variables is correct
- Check firewall settings

### JDBC Driver Errors

- Gradle automatically downloads the JDBC driver from Maven Central
- Check network connection

### Permission Errors

- Verify that the database user has necessary permissions
- Access permissions to system views such as `ALL_TABLES`, `ALL_VIEWS`, `ALL_TAB_COLUMNS` are required

### HTTP Mode Connection Failure

- Verify that the server is running in HTTP mode
- Verify that the server address and port are correct
- Check firewall settings

## References

- Python version: `../python/` directory
- [MCP Java SDK Documentation](https://github.com/modelcontextprotocol/java-sdk)
- [Tibero JDBC Developer Guide](https://docs.tmaxtibero.com/tibero/topics/development/jdbc-developers-guide/introduction-to-tibero-jdbc)
