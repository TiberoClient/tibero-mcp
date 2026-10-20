package tibero.mcp;

import java.util.EnumSet;
import java.util.List;
import java.util.stream.Collectors;

import org.eclipse.jetty.ee10.servlet.FilterHolder;
import org.eclipse.jetty.ee10.servlet.ServletContextHandler;
import org.eclipse.jetty.ee10.servlet.ServletHolder;
import org.eclipse.jetty.server.Server;
import org.eclipse.jetty.server.ServerConnector;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import io.modelcontextprotocol.json.McpJsonDefaults;
import io.modelcontextprotocol.json.McpJsonMapper;
import io.modelcontextprotocol.server.McpServer;
import io.modelcontextprotocol.server.McpServerFeatures;
import io.modelcontextprotocol.server.McpStatelessServerFeatures;
import io.modelcontextprotocol.server.McpSyncServer;
import io.modelcontextprotocol.server.transport.DefaultServerTransportSecurityValidator;
import io.modelcontextprotocol.server.transport.HttpServletStatelessServerTransport;
import io.modelcontextprotocol.server.transport.StdioServerTransportProvider;
import io.modelcontextprotocol.spec.McpSchema;
import jakarta.servlet.DispatcherType;
import tibero.mcp.db.Database;
import tibero.mcp.http.ApiKeyFilter;
import tibero.mcp.tools.TiberoTools;

/**
 * Entry point. Configuration and behaviour match the Python server (python/src/main.py):
 * MCP_TRANSPORT=http (default, stateless Streamable HTTP with JSON responses) or stdio,
 * MCP_READ_ONLY to leave out non-read-only tools, MCP_API_KEYS for authentication.
 */
public final class TiberoMcpServer {

    private static final Logger log = LoggerFactory.getLogger(TiberoMcpServer.class);

    private TiberoMcpServer() {
    }

    public static void main(String[] args) throws Exception {
        Config config = Config.load();
        for (String name : List.of("TIBERO_HOST", "TIBERO_DATABASE", "TIBERO_USER", "TIBERO_PASSWORD")) {
            if (config.get(name) == null) {
                log.error("Missing required environment variables: {}", name);
                System.exit(1);
            }
        }

        McpJsonMapper json = McpJsonDefaults.getMapper();
        Database database = Database.fromConfig(config);
        TiberoTools tools = new TiberoTools(database, json);
        boolean readOnly = config.flag("MCP_READ_ONLY");
        List<TiberoTools.Entry> entries = tools.entries(readOnly);
        if (readOnly) {
            log.info("Read-only mode: tools registered: {}",
                    entries.stream().map(e -> e.tool().name()).collect(Collectors.joining(", ")));
        }

        String transport = config.get("MCP_TRANSPORT", "http").toLowerCase(java.util.Locale.ROOT);
        if (transport.equals("http") || transport.equals("streamable-http")) {
            runHttp(config, json, tools, entries);
        }
        else {
            runStdio(config, json, tools, entries, database);
            System.exit(0);
        }
    }

    private static McpSchema.Implementation implementation(TiberoTools.ServerInfo info) {
        return McpSchema.Implementation.builder(info.name(), info.version()).title(info.title()).build();
    }

    private static McpSchema.ServerCapabilities capabilities() {
        return McpSchema.ServerCapabilities.builder().tools(false).build();
    }

    private static void runStdio(Config config, McpJsonMapper json, TiberoTools tools, List<TiberoTools.Entry> entries,
            Database database) throws InterruptedException {
        log.info("Starting Tibero MCP Server as stdio server");
        TiberoTools.ServerInfo info = tools.serverInfo();
        // Exit when the client closes stdin, as the Python server does, but only after
        // every request read so far has been answered (see StdioDrain).
        StdioDrain drain = new StdioDrain(json, StdioDrain.seconds(config.getInt("TIBERO_QUERY_TIMEOUT", 60) + 30));
        McpSyncServer server = McpServer.sync(new StdioServerTransportProvider(json, drain.input(System.in), drain.output(System.out)))
            .serverInfo(implementation(info))
            .instructions(info.instructions())
            .capabilities(capabilities())
            .tools(entries.stream()
                .map(e -> McpServerFeatures.SyncToolSpecification.builder()
                    .tool(e.tool())
                    .callHandler((exchange, request) -> e.handler().apply(request.arguments()))
                    .build())
                .toList())
            .build();
        drain.awaitFinished();
        server.closeGracefully();
        database.close();
    }

    private static void runHttp(Config config, McpJsonMapper json, TiberoTools tools,
            List<TiberoTools.Entry> entries) throws Exception {
        String host = config.get("MCP_SERVER_HOST", "0.0.0.0");
        int port = config.getInt("MCP_SERVER_PORT", 8000);
        String path = config.get("MCP_HTTP_PATH", "/mcp");
        List<String> keys = config.list("MCP_API_KEYS");

        if (keys.isEmpty()) {
            if (!List.of("127.0.0.1", "localhost", "::1").contains(host) && !config.flag("MCP_ALLOW_ANONYMOUS")) {
                log.error("MCP_API_KEYS is empty while listening on a non-loopback address. "
                        + "Set MCP_API_KEYS, or MCP_ALLOW_ANONYMOUS=true to run without authentication.");
                System.exit(1);
            }
            log.warn("Running without API key authentication");
        }

        HttpServletStatelessServerTransport.Builder transportBuilder = HttpServletStatelessServerTransport.builder()
            .jsonMapper(json)
            .messageEndpoint(path);
        List<String> allowedHosts = config.list("MCP_ALLOWED_HOSTS");
        if (!allowedHosts.isEmpty()) {
            transportBuilder.securityValidator(
                    DefaultServerTransportSecurityValidator.builder().allowedHosts(allowedHosts).build());
        }
        HttpServletStatelessServerTransport transport = transportBuilder.build();

        TiberoTools.ServerInfo info = tools.serverInfo();
        McpServer.sync(transport)
            .serverInfo(implementation(info))
            .instructions(info.instructions())
            .capabilities(capabilities())
            .tools(entries.stream()
                .map(e -> McpStatelessServerFeatures.SyncToolSpecification.builder()
                    .tool(e.tool())
                    .callHandler((context, request) -> e.handler().apply(request.arguments()))
                    .build())
                .toList())
            .build();

        Server server = new Server();
        ServerConnector connector = new ServerConnector(server);
        connector.setHost(host);
        connector.setPort(port);
        server.addConnector(connector);

        ServletContextHandler context = new ServletContextHandler();
        context.setContextPath("/");
        context.addFilter(new FilterHolder(new ApiKeyFilter(keys, path)), "/*", EnumSet.of(DispatcherType.REQUEST));
        context.addServlet(new ServletHolder(transport), "/*");
        server.setHandler(context);

        log.info("Starting Tibero MCP Server (Streamable HTTP) on {}:{}{}", host, port, path);
        server.start();
        server.join();
    }
}
