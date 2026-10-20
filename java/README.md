# Tibero MCP Server (Java)

Tibero DBMS 용 MCP(Model Context Protocol) 서버의 Java 구현이다. 공식 MCP Java SDK(`io.modelcontextprotocol.sdk:mcp` 2.1.0)
위에 Jetty 12 · HikariCP 로 만들었고, **Python 구현(`../python`)과 기능이 같다** — 도구 이름·설명·annotations·입출력
스키마는 저장소 루트의 `spec/tools.json` 하나를 두 구현이 공유하고, 설정 변수·인증·오류 문구·값 변환 규칙도 같다.

## 도구

| 도구 | 성격 | 설명 |
|---|---|---|
| `execute_query` | 읽기 | SELECT / WITH 만. `max_rows`(기본 200, 최대 5000) 초과 시 `truncated: true` |
| `execute_dml` | 쓰기(파괴적) | INSERT·UPDATE·DELETE·MERGE 한 문장을 단독 트랜잭션으로 커밋. DDL 거부. `dry_run=true` 면 롤백 |
| `get_schema` | 읽기 | 표·뷰 목록·주석·통계 행 수(스키마 생략 시 시스템 스키마 제외) |
| `get_table_info` | 읽기 | 컬럼·주석, PK·FK(참조 테이블/컬럼)·UNIQUE·CHECK, 인덱스 컬럼 |
| `explain_plan` | 읽기 | `PLAN_TABLE` 기반 실행계획(한 트랜잭션에서 만들고 읽은 뒤 롤백) |
| `sample_table` | 읽기 | 앞쪽 n 행(기본 10, 최대 1000) |

모든 도구는 `outputSchema` 와 `structuredContent` 를 함께 돌려주고, DB 오류는 `isError` 결과에 Tibero 메시지를 싣는다.
`MCP_READ_ONLY=true` 면 `execute_dml` 은 등록되지 않는다.

## 요구사항

- 빌드: JDK 17 이상 (Gradle 은 wrapper 가 받는다)
- 실행: Java 17 이상
- JDBC 드라이버 `com.tmaxtibero:tbjdbc17:7.2.6` 은 빌드 때 Maven Central 에서 받아 jar 에 포함된다

## 빌드

```bash
cd java
./gradlew shadowJar     # build/libs/tibero-mcp-server-<version>.jar (의존성 포함 단일 jar)
./gradlew test          # 단위 테스트 (spec/conformance/cases.json 벡터 공유)
```

Docker (저장소 루트에서 — 공유 스펙이 `spec/` 에 있다):

```bash
docker build -f java/Dockerfile -t tibero-mcp-java .
docker run -d -p 8000:8000 --env-file mcp.env tibero-mcp-java
```

## 설정

환경 변수, 또는 작업 디렉터리의 `mcp.cfg`(KEY=VALUE, 환경 변수가 우선 — 경로는 `MCP_CONFIG_FILE`)로 준다.
항목은 Python 과 같다(`../python/mcp.cfg.example` 참조).

| 변수 | 기본값 | 설명 |
|---|---|---|
| `TIBERO_HOST` / `TIBERO_PORT` / `TIBERO_DATABASE` | - / `8629` / - | 접속 대상 (필수: HOST·DATABASE·USER·PASSWORD) |
| `TIBERO_USER` / `TIBERO_PASSWORD` | - | 계정 |
| `TIBERO_QUERY_TIMEOUT` | `60` | 문장별 타임아웃(초) |
| `TIBERO_MAX_CELL_CHARS` | `4000` | 셀 값 최대 길이(코드포인트) |
| `TIBERO_SYSTEM_SCHEMAS` | `SYS,SYSCAT,…` | `get_schema` 가 기본으로 빼는 스키마 |
| `MCP_TRANSPORT` | `http` | `http`(stateless Streamable HTTP, JSON 응답) 또는 `stdio` |
| `MCP_SERVER_HOST` / `MCP_SERVER_PORT` / `MCP_HTTP_PATH` | `0.0.0.0` / `8000` / `/mcp` | HTTP 수신 |
| `MCP_API_KEYS` | - | 쉼표 구분 키. 루프백이 아닌 주소면 필수(없으면 기동 거부) |
| `MCP_ALLOW_ANONYMOUS` | `false` | 키 없이 공개 주소로 띄우기(신뢰망 한정) |
| `MCP_READ_ONLY` | `false` | 쓰기 도구 제외 |
| `MCP_ALLOWED_HOSTS` | - | 지정 시 Host 헤더 검사(DNS rebinding 방어) |
| `LOG_LEVEL` | `INFO` | 로그는 stderr 로만 나간다(stdio 의 stdout 은 프로토콜 전용) |

> 0.2.0 부터 기본 전송이 `http` 다(이전 Java 판은 stdio 기본 + `-Dmcp.mode.http`). stdio 로 쓰려면 `MCP_TRANSPORT=stdio`.

## 인증 (HTTP)

같은 키를 `Authorization: Bearer <키>`, `X-API-Key: <키>`, 경로 `/<키>/mcp` 중 아무 데로 보낸다.
접근 로그는 경로 키를 `/<key>/` 로 가린다. `/healthz` 만 인증 없이 열린다.

## 클라이언트 연결

stdio (Cursor `~/.cursor/mcp.json`, Claude Desktop 등):

```json
{
  "mcpServers": {
    "tibero-java": {
      "command": "java",
      "args": ["-jar", "/path/to/tibero-mcp/java/build/libs/tibero-mcp-server-0.2.0.jar"],
      "env": {
        "MCP_TRANSPORT": "stdio",
        "TIBERO_HOST": "localhost",
        "TIBERO_DATABASE": "tibero",
        "TIBERO_USER": "tibero",
        "TIBERO_PASSWORD": "your_password"
      }
    }
  }
}
```

HTTP:

```json
{
  "mcpServers": {
    "tibero-java": {
      "url": "http://your-server:8000/mcp",
      "headers": { "Authorization": "Bearer <MCP_API_KEYS 의 키>" }
    }
  }
}
```

## Python 과의 동등성

- 도구 정의: `spec/tools.json` (Python 에서 `python -m src.spec > ../spec/tools.json` 으로 생성, Java 는 리소스로 읽어 등록)
- 값 변환·SQL 가드: `spec/README.md` 규칙, 벡터 `spec/conformance/cases.json` 을 두 단위 테스트가 공유
- `spec/conformance/test_parity.py` 가 두 서버를 함께 띄워 tools/list·오류·인증·실 DB 결과를 비교한다

## 프로젝트 구조

```
java/
├── src/main/java/tibero/mcp/
│   ├── TiberoMcpServer.java   # 진입점: stdio / HTTP(Jetty) · 읽기 전용 · 키 검사
│   ├── Config.java            # 환경 변수 + mcp.cfg
│   ├── StdioDrain.java        # stdin EOF 를 응답이 끝난 뒤에 넘긴다
│   ├── db/Database.java       # SQL (python/src/db 와 같은 문장)
│   ├── db/SqlRules.java       # 문장 가드·식별자
│   ├── db/JsonValues.java     # JDBC 값 → 공유 JSON 형태
│   ├── tools/TiberoTools.java # spec/tools.json 의 도구 + 핸들러
│   └── http/ApiKeyFilter.java # API 키 인증 · 키를 가린 접근 로그 · /healthz
├── src/test/java/…            # cases.json 벡터 · 스펙 · 필터 테스트
├── Dockerfile                 # 저장소 루트를 컨텍스트로 빌드
└── build.gradle
```

## 참고

- [Tibero JDBC 개발 가이드](https://docs.tmaxtibero.com/tibero/topics/development/jdbc-developers-guide/introduction-to-tibero-jdbc)
- [MCP Java SDK](https://github.com/modelcontextprotocol/java-sdk)
