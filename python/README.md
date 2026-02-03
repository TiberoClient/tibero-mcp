# Tibero MCP Server (Python)

Tibero DBMS를 위한 MCP(Model Context Protocol) 서버입니다. Python으로 구현되었습니다.

## 주요 기능

이 MCP 서버는 다음과 같은 도구들을 제공합니다:

### 1. **execute_query** - SELECT 쿼리 실행
- SELECT 쿼리를 실행하고 결과를 JSON 배열로 반환
- 파라미터화된 쿼리 지원
- 모든 행을 딕셔너리 형태로 반환

### 2. **execute_dml** - DML 문 실행
- INSERT, UPDATE, DELETE 문 실행
- 자동 트랜잭션 관리 (성공 시 커밋, 실패 시 롤백)
- 영향받은 행 수 반환

### 3. **get_schema** - 스키마 정보 조회
- 데이터베이스의 모든 테이블과 뷰 목록 조회
- 각 테이블/뷰의 comment 포함
- 특정 스키마로 필터링 가능
- 테이블스페이스, 행 수, 마지막 분석 날짜 등 메타데이터 포함

### 4. **get_table_info** - 테이블/뷰 상세 정보
- 특정 테이블 또는 뷰의 상세 정보 조회
- **컬럼 정보**: 이름, 데이터 타입, 길이, 정밀도, NULL 허용 여부, 기본값, **컬럼 comment**
- **제약 조건**: 제약 이름, 타입, 상태 등
- **인덱스**: 인덱스 이름, 타입, 유일성, 상태 등
- 테이블과 뷰 모두 지원 (뷰의 경우 제약조건/인덱스는 보통 빈 배열)

### 5. **explain_plan** - 실행 계획 조회
- SQL 쿼리의 실행 계획을 실제 실행 없이 분석
- 실행 가능한 SQL인지 검증
- 실행 계획 상세 정보 반환 (DBMS_XPLAN.DISPLAY 또는 PLAN_TABLE 사용)
- SQL이 유효하지 않은 경우 에러 메시지 반환

### 6. **sample_table** - 테이블 샘플링
- 특정 테이블에서 n개의 행을 샘플링
- 전체 데이터를 로드하지 않고 필요한 행만 조회
- 기본값: 10개, 최대값: 1000개
- 테이블 구조와 데이터를 빠르게 확인하는 데 유용

## 요구사항

- Python 3.12 이상
- Java JDK 8 이상 (JDBC 드라이버 실행용)
- Tibero DBMS
- Tibero JDBC 드라이버 (tbjdbc8*.jar)

## 설치

### 1. 저장소 클론

```bash
git clone <repository-url>
cd tibero-mcp/python
```

### 2. 의존성 설치

```bash
pip install -r requirements.txt
```

### 3. JDBC 드라이버 준비

Tibero JDBC 드라이버를 `lib/` 디렉토리에 배치하세요:

- 파일: `lib/tbjdbc8-7.2.4.jar` (또는 `tbjdbc8*.jar` 패턴의 파일)
- JDBC 드라이버는 Tibero 설치 디렉토리에서 찾을 수 있습니다

### 4. 환경 변수 설정

`mcp.cfg.example` 파일을 복사하여 `mcp.cfg` 파일을 생성하고 데이터베이스 연결 정보를 입력하세요:

```bash
# Windows
copy mcp.cfg.example mcp.cfg

# Linux/Mac
cp mcp.cfg.example mcp.cfg
```

`mcp.cfg` 파일을 편집하여 Tibero 데이터베이스 연결 정보를 설정하세요:

```ini
# Tibero Database Connection
TIBERO_HOST=your_host
TIBERO_PORT=8629
TIBERO_DATABASE=your_database
TIBERO_USER=your_username
TIBERO_PASSWORD=your_password

# MCP Server Configuration
MCP_TRANSPORT=http          # http (기본값) 또는 stdio
MCP_SERVER_HOST=0.0.0.0     # 0.0.0.0: 모든 인터페이스, localhost: 로컬만
MCP_SERVER_PORT=8000        # HTTP 서버 포트
LOG_LEVEL=INFO
```

## 실행

```bash
python -m src.main
```

서버는 `mcp.cfg`의 `MCP_TRANSPORT` 설정에 따라 두 가지 방식으로 실행됩니다 (기본값: http):

### 1. HTTP 서버 방식 (기본값)

설정을 생략하거나 `MCP_TRANSPORT=http`로 설정하면 HTTP 서버로 실행됩니다.

**특징:**
- 원격 클라이언트에서 접근 가능
- 여러 클라이언트가 동시에 연결 가능
- 네트워크를 통한 통신

**시작 메시지:**
```
Starting Tibero MCP Server as Streamable HTTP server on 0.0.0.0:8000
Server will be accessible at: http://0.0.0.0:8000
MCP endpoint: http://0.0.0.0:8000/mcp
```

### 2. stdio 서버 방식

`MCP_TRANSPORT=stdio`로 설정하면 stdio 서버로 실행됩니다.

**시작 메시지:**
```
Starting Tibero MCP Server as stdio server
Server will communicate via stdin/stdout
```

**서버 종료:**
- 터미널에서 `Ctrl + C`를 눌러 서버를 종료합니다.

## Cursor 연결 설정

### HTTP 서버 방식 연결

원격 HTTP 서버에 연결하려면 `~/.cursor/mcp.json` 파일을 다음과 같이 설정하세요:

```json
{
  "mcpServers": {
    "tibero": {
      "url": "http://your-server-ip:8000/mcp"
    }
  }
}
```

**로컬 서버 연결:**
```json
{
  "mcpServers": {
    "tibero": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

### stdio 서버 방식 연결

로컬 stdio 서버에 연결하려면 `~/.cursor/mcp.json` 파일을 다음과 같이 설정하세요:

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

설정 후 Cursor를 재시작하면 MCP 도구들을 사용할 수 있습니다.

## 프로젝트 구조

```
python/
├── src/
│   ├── db/                      # 데이터베이스 모듈
│   │   ├── __init__.py
│   │   ├── connector.py         # JDBC 연결 관리
│   │   ├── query_executor.py    # 쿼리 실행 및 실행 계획
│   │   └── schema_viewer.py     # 스키마 정보 조회
│   ├── mcp/                     # MCP 서버
│   │   ├── __init__.py
│   │   └── server.py            # FastMCP 서버 및 도구 정의
│   └── main.py                  # 진입점
├── lib/                         # JDBC 드라이버
│   └── tbjdbc8-7.2.4.jar
├── mcp.cfg.example              # 설정 파일 예제
├── requirements.txt             # Python 의존성
└── README.md                    # 이 파일
```

## 문제 해결

### 연결 오류

- Tibero 데이터베이스가 실행 중인지 확인하세요
- `mcp.cfg` 파일의 연결 정보가 올바른지 확인하세요
- 방화벽 설정을 확인하세요 (HTTP 서버 방식의 경우)

### JDBC 드라이버 오류

- `lib/` 디렉토리에 `tbjdbc8*.jar` 파일이 있는지 확인하세요
- Java JDK가 설치되어 있고 `JAVA_HOME`이 설정되어 있는지 확인하세요

### 권한 오류

- 데이터베이스 사용자에게 필요한 권한이 있는지 확인하세요
- `ALL_TABLES`, `ALL_VIEWS`, `ALL_TAB_COLUMNS` 등의 시스템 뷰에 대한 접근 권한이 필요합니다

