# Tibero MCP Server (Python)

Tibero DBMS를 위한 MCP(Model Context Protocol) 서버입니다. Python으로 구현되었습니다.

## 주요 기능

MCP SDK 2.x(`MCPServer`, 프로토콜 2026-07-28) 기반이다. 모든 도구에 MCP tool annotations
(`readOnlyHint`·`destructiveHint`·`idempotentHint`·`openWorldHint`·`title`)와 반환 모델이 선언돼 있어
클라이언트는 `outputSchema` 와 `structuredContent` 를 함께 받는다. DB 오류는 `isError` 결과로 Tibero
메시지(예: `JDBC-8026`)를 그대로 돌려줘 모델이 SQL 을 고칠 수 있다.

| 도구 | 성격 | 설명 |
|---|---|---|
| `execute_query` | 읽기 | SELECT / WITH 만 허용. `max_rows`(기본 200, 최대 5000) 초과 시 `truncated: true` |
| `execute_dml` | 쓰기(파괴적) | INSERT·UPDATE·DELETE·MERGE 한 문장을 단독 트랜잭션으로 커밋. DDL 거부. `dry_run=true` 면 영향 행 수만 보고 롤백 |
| `get_schema` | 읽기 | 표·뷰 목록과 주석·통계 행 수. 스키마를 생략하면 시스템 스키마(`TIBERO_SYSTEM_SCHEMAS`)를 뺀 전체 |
| `get_table_info` | 읽기 | 컬럼·주석, 제약(PK·FK 의 참조 테이블/컬럼·UNIQUE·CHECK), 인덱스 컬럼 |
| `explain_plan` | 읽기 | `PLAN_TABLE` 기반 실행계획(Tibero 에는 `DBMS_XPLAN` 이 없다). 한 트랜잭션에서 만들고 읽은 뒤 롤백 |
| `sample_table` | 읽기 | 앞쪽 n 행(기본 10, 최대 1000) |

- 문장 끝 `;` 는 떼고 실행한다. 모든 문장에 서버측 타임아웃(`TIBERO_QUERY_TIMEOUT`, 기본 60초)을 건다
- 표 이름은 정확한 이름 → 대문자 순으로 찾는다(따옴표 없이 만든 이름은 대문자로 저장된다)
- 긴 셀 값은 `TIBERO_MAX_CELL_CHARS`(기본 4000자)에서 자른다
- JDBC 호출은 워커 스레드에서 돌아 이벤트 루프를 막지 않는다
- 도구 annotations 는 힌트일 뿐이다. 실제 쓰기 차단은 **DB 계정 권한**으로 건다(읽기 전용 계정 권장)

## 요구사항

- Python 3.12 이상 (Docker 이미지는 3.13)
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

`mcp.cfg.example` 을 `mcp.cfg` 로 복사해 채운다(환경 변수가 있으면 그쪽이 우선). 항목 설명은 예제 파일 주석에 있다.

```bash
cp mcp.cfg.example mcp.cfg
```

## 인증

HTTP 모드에서 루프백이 아닌 주소로 열면 `MCP_API_KEYS` 가 필수다(없으면 기동하지 않는다.
신뢰망 한정으로 `MCP_ALLOW_ANONYMOUS=true`). 같은 키를 세 곳 중 아무 데나 실어 보내면 된다:

| 방식 | 예 | 쓰는 곳 |
|---|---|---|
| `Authorization: Bearer <키>` | 헤더 | Claude 커스텀 커넥터 "Request headers", Claude Code, Cursor |
| `X-API-Key: <키>` | 헤더 | 사용자 정의 헤더만 받는 클라이언트 |
| 경로 키 | `https://host/<키>/mcp` | URL 만 받는 클라이언트(ChatGPT 커넥터 "No authentication" 등) |

경로 키는 URL 에 남으므로 서버 접근 로그는 키를 `/<key>/` 로 가려 찍고(uvicorn 기본 접근 로그는 끈다),
앞단 프록시에서도 그 location 의 access log 를 꺼야 한다. 키는 `openssl rand -hex 32` 로 만들고,
교체할 때는 쉼표로 새 키를 함께 넣었다가 옛 키를 뺀다.

## Docker

```bash
docker build -t tibero-mcp .          # lib/tbjdbc8*.jar 가 있어야 한다
docker run -d -p 8000:8000 --env-file mcp.env tibero-mcp
curl http://localhost:8000/healthz    # 인증 없이 열리는 유일한 경로
```

서버는 stateless Streamable HTTP + JSON 응답으로 동작한다 — 요청마다 독립이라 리버스 프록시 뒤나
재시작 뒤에도 세션이 끊기지 않는다. 프록시에 경로 접두사를 붙이면(`location /tiberomcp/ { proxy_pass http://…:8000/; }`)
엔드포인트는 `https://host/tiberomcp/mcp` 가 된다.

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
      "url": "http://your-server-ip:8000/mcp",
      "headers": { "Authorization": "Bearer <MCP_API_KEYS 의 키>" }
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
│   │   ├── auth.py              # API 키 인증·키를 가린 접근 로그
│   │   └── server.py            # MCPServer 와 도구 정의
│   └── main.py                  # 진입점
├── lib/                         # JDBC 드라이버
│   └── tbjdbc8-7.2.4.jar
├── mcp.cfg.example              # 설정 파일 예제
├── tests/                       # 단위 테스트(SQL 가드·인증), DB 불필요
├── Dockerfile
├── requirements.txt             # Python 의존성(== 고정)
├── requirements-dev.txt         # + pytest
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

