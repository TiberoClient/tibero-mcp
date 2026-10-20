FROM python:3.13-slim

# JPype loads libjvm from JAVA_HOME to drive the Tibero JDBC driver.
RUN apt-get update \
    && apt-get install -y --no-install-recommends default-jre-headless \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s "$(dirname "$(dirname "$(readlink -f "$(command -v java)")")")" /opt/java
ENV JAVA_HOME=/opt/java \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Same driver and version as the Java server (com.tmaxtibero:tbjdbc17 in java/build.gradle).
ARG TBJDBC_VERSION=7.2.6
ARG TBJDBC_SHA256=2e8ad3e9bdb8bfb8c2cdc03692f504e3f43c8b7f7c546fc705ffb37785425de2
RUN mkdir lib && python -c "import urllib.request; urllib.request.urlretrieve('https://repo1.maven.org/maven2/com/tmaxtibero/tbjdbc17/${TBJDBC_VERSION}/tbjdbc17-${TBJDBC_VERSION}.jar', 'lib/tbjdbc17-${TBJDBC_VERSION}.jar')" \
    && echo "${TBJDBC_SHA256}  lib/tbjdbc17-${TBJDBC_VERSION}.jar" | sha256sum -c -

COPY src/ src/

RUN useradd --system --uid 10001 --no-create-home mcp
USER mcp

ENV MCP_TRANSPORT=http \
    MCP_SERVER_HOST=0.0.0.0 \
    MCP_SERVER_PORT=8000
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status == 200 else 1)"

CMD ["python", "-m", "src.main"]
