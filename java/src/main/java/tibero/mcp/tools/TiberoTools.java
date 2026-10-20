package tibero.mcp.tools;

import java.io.IOException;
import java.io.InputStream;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Function;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import io.modelcontextprotocol.json.McpJsonMapper;
import io.modelcontextprotocol.json.TypeRef;
import io.modelcontextprotocol.spec.McpSchema;
import io.modelcontextprotocol.spec.McpSchema.CallToolResult;
import tibero.mcp.ToolException;
import tibero.mcp.db.Database;

/**
 * Tool definitions and handlers.
 *
 * Names, descriptions, annotations and input/output schemas come from the shared
 * spec (spec/tools.json, exported from the Python server) rather than being declared
 * here, so the two implementations cannot drift. Handlers return the same structured
 * results as the Python pydantic models in python/src/mcp/server.py.
 */
public class TiberoTools {

    private static final Logger log = LoggerFactory.getLogger(TiberoTools.class);

    /** A spec tool paired with its handler. */
    public record Entry(McpSchema.Tool tool, Function<Map<String, Object>, CallToolResult> handler) {
    }

    /** Server identity and instructions from the spec. */
    public record ServerInfo(String name, String title, String version, String instructions) {
    }

    @FunctionalInterface
    private interface Handler {

        Map<String, Object> apply(Map<String, Object> args) throws SQLException;

    }

    private final Database database;

    private final McpJsonMapper json;

    private final Map<String, Object> spec;

    public TiberoTools(Database database, McpJsonMapper json) {
        this.database = database;
        this.json = json;
        this.spec = loadSpec(json);
    }

    public static Map<String, Object> loadSpec(McpJsonMapper json) {
        try (InputStream in = TiberoTools.class.getResourceAsStream("/tools.json")) {
            if (in == null) {
                throw new IllegalStateException("tools.json missing from the classpath");
            }
            return json.readValue(in.readAllBytes(), new TypeRef<Map<String, Object>>() {
            });
        }
        catch (IOException e) {
            throw new IllegalStateException("Cannot read tools.json: " + e.getMessage(), e);
        }
    }

    @SuppressWarnings("unchecked")
    public ServerInfo serverInfo() {
        Map<String, Object> server = (Map<String, Object>) spec.get("server");
        return new ServerInfo((String) server.get("name"), (String) server.get("title"),
                (String) server.get("version"), (String) server.get("instructions"));
    }

    /**
     * Every spec tool with its handler. In read-only mode only tools annotated
     * readOnlyHint=true are returned, the same rule the Python server applies.
     */
    @SuppressWarnings("unchecked")
    public List<Entry> entries(boolean readOnly) {
        Map<String, Handler> handlers = Map.of("execute_query", this::executeQuery, "execute_dml", this::executeDml,
                "get_schema", this::getSchema, "get_table_info", this::getTableInfo, "explain_plan",
                this::explainPlan, "sample_table", this::sampleTable);
        List<Entry> result = new ArrayList<>();
        for (Map<String, Object> raw : (List<Map<String, Object>>) spec.get("tools")) {
            McpSchema.Tool tool = json.convertValue(raw, McpSchema.Tool.class);
            Handler handler = handlers.get(tool.name());
            if (handler == null) {
                throw new IllegalStateException("No handler for spec tool " + tool.name());
            }
            if (readOnly && !(tool.annotations() != null && Boolean.TRUE.equals(tool.annotations().readOnlyHint()))) {
                continue;
            }
            result.add(new Entry(tool, args -> call(tool, handler, args)));
        }
        if (result.size() + (readOnly ? 1 : 0) < handlers.size()) {
            throw new IllegalStateException("Handlers without a spec tool: " + handlers.keySet());
        }
        return result;
    }

    // ----- dispatch and error shape (matches the Python SDK's ToolError results) -----

    private CallToolResult call(McpSchema.Tool tool, Handler handler, Map<String, Object> rawArgs) {
        Map<String, Object> args = withDefaults(tool, rawArgs == null ? Map.of() : rawArgs);
        try {
            Map<String, Object> structured = handler.apply(args);
            return CallToolResult.builder()
                .structuredContent(structured)
                .addTextContent(json.writeValueAsString(structured))
                .isError(false)
                .build();
        }
        catch (ToolException e) {
            return error(tool.name(), e.getMessage());
        }
        catch (Exception e) {
            String message = e.getMessage() == null ? e.getClass().getSimpleName() : e.toString();
            log.warn("Database call failed: {}", message);
            return error(tool.name(), "Database error: " + message);
        }
    }

    private static CallToolResult error(String toolName, String message) {
        return CallToolResult.builder()
            .addTextContent("Error executing tool " + toolName + ": " + message)
            .isError(true)
            .build();
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> withDefaults(McpSchema.Tool tool, Map<String, Object> args) {
        Map<String, Object> merged = new LinkedHashMap<>();
        Map<String, Object> properties = (Map<String, Object>) tool.inputSchema().getOrDefault("properties", Map.of());
        properties.forEach((name, schema) -> {
            Map<String, Object> property = (Map<String, Object>) schema;
            if (property.containsKey("default")) {
                merged.put(name, property.get("default"));
            }
        });
        merged.putAll(args);
        return merged;
    }

    private static String str(Map<String, Object> args, String name) {
        Object value = args.get(name);
        return value == null ? null : value.toString();
    }

    private static int integer(Map<String, Object> args, String name) {
        return ((Number) args.get(name)).intValue();
    }

    private static Double toDouble(Object value) {
        if (value == null) {
            return null;
        }
        return value instanceof Number number ? number.doubleValue() : Double.parseDouble(value.toString());
    }

    private static Integer toInteger(Object value) {
        if (value == null) {
            return null;
        }
        return value instanceof Number number ? number.intValue() : Integer.parseInt(value.toString());
    }

    // ----- tools -----

    private Map<String, Object> executeQuery(Map<String, Object> args) throws SQLException {
        String query = str(args, "query");
        log.info("execute_query: {}", PyText.head(query, 200));
        Database.Page page = database.runSelect(query, integer(args, "max_rows"));
        return queryResult(page.columns(), page.rows(), page.truncated());
    }

    private Map<String, Object> executeDml(Map<String, Object> args) throws SQLException {
        String query = str(args, "query");
        boolean dryRun = Boolean.TRUE.equals(args.get("dry_run"));
        log.info("execute_dml (dry_run={}): {}", dryRun, PyText.head(query, 200));
        long rowcount = database.executeDml(query, dryRun);
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("rowcount", rowcount);
        result.put("committed", !dryRun);
        return result;
    }

    private Map<String, Object> getSchema(Map<String, Object> args) throws SQLException {
        List<Map<String, Object>> objects = new ArrayList<>();
        for (Map<String, Object> row : database.getSchemaInfo(str(args, "schema_name"))) {
            Map<String, Object> object = new LinkedHashMap<>();
            object.put("schema_name", row.get("SCHEMA_NAME"));
            object.put("object_name", row.get("OBJECT_NAME"));
            object.put("object_type", row.get("OBJECT_TYPE"));
            object.put("num_rows", toLongOrNull(row.get("NUM_ROWS")));
            object.put("last_analyzed", row.get("LAST_ANALYZED"));
            object.put("comments", row.get("COMMENTS"));
            objects.add(object);
        }
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("objects", objects);
        result.put("count", objects.size());
        return result;
    }

    private static Long toLongOrNull(Object value) {
        if (value == null) {
            return null;
        }
        return value instanceof Number number ? number.longValue() : Long.parseLong(value.toString());
    }

    private Map<String, Object> resolve(Map<String, Object> args) throws SQLException {
        String schema = str(args, "schema_name");
        String table = str(args, "table_name");
        Map<String, Object> found = database.resolveObject(schema, table);
        if (found == null) {
            throw new ToolException(schema + "." + table + " does not exist or is not visible to this account.");
        }
        return found;
    }

    private Map<String, Object> getTableInfo(Map<String, Object> args) throws SQLException {
        Map<String, Object> found = resolve(args);
        String owner = (String) found.get("OWNER");
        String name = (String) found.get("OBJECT_NAME");
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("schema_name", owner);
        result.put("table_name", name);
        result.put("object_type", found.get("OBJECT_TYPE"));
        result.put("comments", found.get("COMMENTS"));
        result.put("columns", database.getTableColumns(owner, name));
        result.put("constraints", database.getTableConstraints(owner, name));
        result.put("indexes", database.getTableIndexes(owner, name));
        return result;
    }

    private Map<String, Object> explainPlan(Map<String, Object> args) throws SQLException {
        String query = str(args, "query");
        log.info("explain_plan: {}", PyText.head(query, 200));
        List<Map<String, Object>> steps = new ArrayList<>();
        for (Map<String, Object> row : database.explainPlan(query)) {
            Map<String, Object> step = new LinkedHashMap<>();
            step.put("id", toInteger(row.get("ID")));
            step.put("parent_id", toInteger(row.get("PARENT_ID")));
            step.put("depth", toInteger(row.get("DEPTH")));
            step.put("operation", row.get("OPERATION"));
            step.put("object_owner", row.get("OBJECT_OWNER"));
            step.put("object_name", row.get("OBJECT_NAME"));
            step.put("cost", toDouble(row.get("COST")));
            step.put("cardinality", toDouble(row.get("CARDINALITY")));
            step.put("access_predicates", row.get("ACCESS_PREDICATES"));
            step.put("filter_predicates", row.get("FILTER_PREDICATES"));
            steps.add(step);
        }
        if (steps.isEmpty()) {
            throw new ToolException("The database produced no plan rows for this statement.");
        }
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("steps", steps);
        result.put("total_cost", steps.get(0).get("cost"));
        result.put("plan_text", planText(steps));
        return result;
    }

    /** Same layout as python/src/mcp/server.py {@code _plan_text}, including Python's number formatting. */
    static String planText(List<Map<String, Object>> steps) {
        List<String> lines = new ArrayList<>();
        for (Map<String, Object> step : steps) {
            int depth = step.get("depth") == null ? 0 : (Integer) step.get("depth");
            String indent = "  ".repeat(Math.max(0, depth));
            List<String> parts = new ArrayList<>();
            for (Object part : new Object[] { step.get("object_owner"), step.get("object_name") }) {
                if (part != null && !part.toString().isEmpty()) {
                    parts.add(part.toString());
                }
            }
            String target = String.join(".", parts);
            String detail = target.isEmpty() ? "" : " " + target;
            String stats = step.get("cost") == null ? ""
                    : " (cost=" + PyText.repr(step.get("cost")) + ", rows=" + PyText.repr(step.get("cardinality")) + ")";
            lines.add(indent + step.get("id") + " " + PyText.repr(step.get("operation")) + detail + stats);
            for (String label : new String[] { "access", "filter" }) {
                Object predicate = step.get(label + "_predicates");
                if (predicate != null && !predicate.toString().isEmpty()) {
                    lines.add("  ".repeat(Math.max(0, depth + 1)) + label + ": " + predicate);
                }
            }
        }
        return String.join("\n", lines);
    }

    private Map<String, Object> sampleTable(Map<String, Object> args) throws SQLException {
        Map<String, Object> found = resolve(args);
        String owner = (String) found.get("OWNER");
        String name = (String) found.get("OBJECT_NAME");
        List<Map<String, Object>> rows = database.sampleTableRows(owner, name, integer(args, "limit"));
        List<String> columns = new ArrayList<>();
        if (!rows.isEmpty()) {
            columns.addAll(rows.get(0).keySet());
        }
        else {
            for (Map<String, Object> column : database.getTableColumns(owner, name)) {
                columns.add((String) column.get("COLUMN_NAME"));
            }
        }
        return queryResult(columns, rows, false);
    }

    private static Map<String, Object> queryResult(List<String> columns, List<Map<String, Object>> rows,
            boolean truncated) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("columns", columns);
        result.put("rows", rows);
        result.put("row_count", rows.size());
        result.put("truncated", truncated);
        return result;
    }
}
