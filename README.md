# Tibero MCP Server

Tibero DBMS를 위한 MCP(Model Context Protocol) 서버 프로젝트입니다. Python과 Java 두 가지 구현을 제공합니다.

## 프로젝트 구조

이 프로젝트는 multi-module 구조로 구성되어 있으며, 각 모듈은 독립적인 프로젝트입니다:

```
tibero-mcp/
├── python/                    # Python MCP 서버 프로젝트
│   ├── src/                   # Python 소스 코드
│   ├── lib/                   # JDBC 드라이버
│   ├── mcp.cfg                # 설정 파일
│   ├── requirements.txt       # Python 의존성
│   └── README.md              # Python 프로젝트 문서
├── java/                      # Java MCP 서버 프로젝트
│   ├── src/                   # Java 소스 코드
│   ├── build.gradle           # Gradle 빌드 설정
│   └── README.md              # Java 프로젝트 문서
└── README.md                  # 이 파일 (전체 프로젝트 개요)
```

## 모듈

### Python 모듈

Python으로 구현된 Tibero MCP 서버입니다.

**주요 기능:**
- SELECT 쿼리 실행
- DML 문 실행 (INSERT, UPDATE, DELETE)
- 스키마 정보 조회
- 테이블/뷰 상세 정보 조회
- 실행 계획 조회
- 테이블 샘플링

**문서:** [python/README.md](python/README.md)

### Java 모듈

Java Spring Boot로 구현된 Tibero MCP 서버입니다. Python 버전과 동일한 기능을 제공합니다.

**주요 기능:**
- SELECT 쿼리 실행
- DML 문 실행 (INSERT, UPDATE, DELETE)
- 스키마 정보 조회
- 테이블/뷰 상세 정보 조회
- 실행 계획 조회
- 테이블 샘플링

**문서:** [java/README.md](java/README.md)

## 시작하기

각 모듈은 독립적인 프로젝트이므로, 사용하려는 모듈의 디렉토리로 이동하여 해당 모듈의 README를 참조하세요:

- **Python 모듈 사용:** `cd python` 후 [python/README.md](python/README.md) 참조
- **Java 모듈 사용:** `cd java` 후 [java/README.md](java/README.md) 참조

