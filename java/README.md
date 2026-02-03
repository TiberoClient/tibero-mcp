# Tibero MCP Server (Java)

Tibero DBMS를 위한 MCP(Model Context Protocol) 서버입니다. Java로 구현되었습니다.

## 개요

이 프로젝트는 Java 기반 티베로 MCP 서버입니다. STDIO와 HTTP 두 가지 모드를 지원합니다.

## 주요 기능

- **execute_query** - SELECT 쿼리 실행
- **execute_dml** - DML 문 실행 (INSERT, UPDATE, DELETE)
- **get_schema** - 스키마 정보 조회
- **get_table_info** - 테이블/뷰 상세 정보
- **explain_plan** - 실행 계획 조회
- **sample_table** - 테이블 샘플링

## 요구사항

- Java JDK 17 이상
- Gradle 7.0 이상 (빌드 도구)
- Tibero DBMS
- Tibero JDBC 드라이버 (Maven Central에서 자동 다운로드)

## 빠른 시작

### 1. 빌드

```bash
./gradlew clean build
```

빌드된 JAR 파일: `build/libs/tibero-mcp-server-{version}.jar`

### 2. 데이터베이스 접속 정보 설정

환경 변수로 설정 (권장):

| 환경 변수 | 설명 | 기본값 | 필수 |
|---------|------|--------|------|
| `TIBERO_HOST` | 데이터베이스 호스트 | `localhost` | ❌ |
| `TIBERO_PORT` | 데이터베이스 포트 | `8629` | ❌ |
| `TIBERO_DATABASE` | 데이터베이스 이름 | `tibero` | ❌ |
| `TIBERO_USER` | 사용자명 | `tibero` | ❌ |
| `TIBERO_PASSWORD` | 비밀번호 | - | ✅ |

**설정 예시:**

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

또는 `src/main/resources/application.yml` 파일에서 직접 설정:

```yaml
spring:
  datasource:
    host: localhost
    port: 8629
    database: tibero
    username: tibero
    password: your_password
```

또는 **Cursor 설정 파일(`~/.cursor/mcp.json`)에서 `env` 필드로 직접 설정** (가장 편리한 방법):

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

> **참고**: 
> - 환경 변수가 설정되어 있으면 환경 변수 값이 우선 적용됩니다
> - Cursor 설정 파일의 `env` 필드 값이 시스템 환경 변수보다 우선 적용됩니다
> - Cursor 설정 파일에 직접 설정하면 시스템 환경 변수를 설정할 필요가 없어 더 편리합니다

### 3. 실행 모드 선택

이 MCP 서버는 두 가지 실행 모드를 지원합니다:

| 모드 | 설명 | 실행 주체 | 사용 시나리오 |
|------|------|----------|-------------|
| **STDIO** | stdin/stdout을 통한 통신 | Cursor가 자동 실행 | 로컬 개발, 단일 사용자 |
| **HTTP** | HTTP 서버로 실행 | 사용자가 직접 실행 | 원격 접근, 다중 사용자 |

> **중요**: 
> - **STDIO 모드**: Cursor가 자동으로 프로세스를 실행하므로 **사용자가 직접 실행할 필요가 없습니다**. Cursor 설정만 하면 됩니다.
> - **HTTP 모드**: **사용자가 미리 서버를 실행해놔야** Cursor에서 연결할 수 있습니다.

#### STDIO 모드 (기본, 권장)

Cursor가 자동으로 프로세스를 실행하므로 별도 실행이 필요 없습니다. Cursor 연결 설정만 하면 됩니다.

> **참고**: 테스트 목적으로 직접 실행하려면:
> ```bash
> java -jar build/libs/tibero-mcp-server-{version}.jar
> # 또는 개발 중
> ./gradlew run
> ```

#### HTTP 모드

**사용자가 직접 서버를 실행해야 합니다.**

1. `src/main/resources/application.yml` 설정:

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
  port: 8080  # 기본값
```

2. 서버 실행:

```bash
# JAR 실행
java -Dmcp.mode.http=true -jar build/libs/tibero-mcp-server-{version}.jar

# 또는 개발 중
./gradlew run -Dmcp.mode.http=true
```

서버가 시작되면 `http://localhost:8080`에서 접근 가능합니다. **이 서버를 계속 실행 상태로 유지**해야 Cursor에서 연결할 수 있습니다.

## Cursor 연결 설정

`~/.cursor/mcp.json` 파일에 다음 설정을 추가하세요:

### STDIO 모드 (권장)

**Cursor가 자동으로 프로세스를 실행합니다.** 사용자가 별도로 프로세스를 실행할 필요가 없습니다.

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

**환경 변수를 JSON에 직접 설정 (권장):**

환경 변수를 시스템에 설정하지 않고, Cursor 설정 파일에 직접 포함할 수 있습니다:

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

> **참고**: 
> - `{version}`을 실제 버전 번호로 교체하세요 (예: `0.0.1`)
> - `env` 필드를 사용하면 시스템 환경 변수를 설정하지 않아도 됩니다
> - `env` 필드의 환경 변수가 시스템 환경 변수보다 우선 적용됩니다
> - 설정 후 Cursor를 재시작하면 자동으로 연결됩니다

### HTTP 모드

**⚠️ 주의: HTTP 모드로 연결하려면 먼저 서버를 실행해야 합니다.** (위의 "HTTP 모드" 실행 방법 참조)

**로컬 서버:**

```json
{
  "mcpServers": {
    "tibero-java-http": {
      "url": "http://localhost:8080"
    }
  }
}
```

**원격 서버:**

```json
{
  "mcpServers": {
    "tibero-java-http": {
      "url": "http://your-server-ip:8080"
    }
  }
}
```

> **참고**: 
> - 서버가 실행 중이어야 연결할 수 있습니다
> - 서버 주소와 포트가 올바른지 확인하세요
> - 방화벽 설정을 확인하세요

## 프로젝트 구조

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

## 기술 스택

- **Java 17+**: 최소 요구 Java 버전
- **Spring Boot 3.5.3**: 애플리케이션 프레임워크
- **Spring AI MCP Server**: MCP 프로토콜 구현
- **Tibero JDBC Driver 7.2.4**: Tibero 데이터베이스 연결
- **HikariCP**: 커넥션 풀
- **Gradle**: 빌드 도구

## 문제 해결

### 연결 오류

- Tibero 데이터베이스가 실행 중인지 확인
- 환경 변수의 연결 정보가 올바른지 확인
- 방화벽 설정 확인

### JDBC 드라이버 오류

- Gradle이 Maven Central에서 자동으로 JDBC 드라이버를 다운로드합니다
- 네트워크 연결 확인

### 권한 오류

- 데이터베이스 사용자에게 필요한 권한이 있는지 확인
- `ALL_TABLES`, `ALL_VIEWS`, `ALL_TAB_COLUMNS` 등의 시스템 뷰에 대한 접근 권한 필요

### HTTP 모드 연결 실패

- 서버가 HTTP 모드로 실행 중인지 확인
- 서버 주소와 포트가 올바른지 확인
- 방화벽 설정 확인

## 참고 자료

- Python 버전: `../python/` 디렉토리
- [MCP Java SDK 문서](https://github.com/modelcontextprotocol/java-sdk)
- [Tibero JDBC 개발 가이드](https://docs.tmaxtibero.com/tibero/topics/development/jdbc-developers-guide/introduction-to-tibero-jdbc)
