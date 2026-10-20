# Build from the repository root (the shared spec lives in ../spec):
#   docker build -f java/Dockerfile -t tibero-mcp-java .
FROM eclipse-temurin:21-jdk AS build
WORKDIR /src
COPY spec/ spec/
COPY java/ java/
WORKDIR /src/java
RUN ./gradlew --no-daemon -q shadowJar

FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=build /src/java/build/libs/tibero-mcp-server-*.jar /app/tibero-mcp-server.jar
RUN useradd --system --uid 10001 --no-create-home mcp
USER mcp
ENV MCP_TRANSPORT=http \
    MCP_SERVER_HOST=0.0.0.0 \
    MCP_SERVER_PORT=8000
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD ["sh", "-c", "exec 3<>/dev/tcp/127.0.0.1/8000 && printf 'GET /healthz HTTP/1.0\\r\\n\\r\\n' >&3 && grep -q '200' <&3"]
CMD ["java", "-jar", "/app/tibero-mcp-server.jar"]
