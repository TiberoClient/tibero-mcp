package tibero.mcp.tools;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Component;
import org.springaicommunity.mcp.annotation.McpTool;
import org.springaicommunity.mcp.annotation.McpToolParam;
import tibero.mcp.db.DatabaseService;

import java.util.*;

@Component
public class GetSchemaTool {

    private static final String DESCRIPTION = """
            Get schema information for the database including tables and views with comments.
            
            Note: Table and view names returned in OBJECT_NAME are case-sensitive as defined 
            in the schema. If a table/view was created with quoted identifiers (e.g., "atom", 
            "Country", "Player_Attributes"), the OBJECT_NAME will reflect the exact case. 
            When using these names in other tools, use the exact case as shown in OBJECT_NAME.
            
            Returns JSON string with schema information (tables and views) including:
            - SCHEMA_NAME: Schema/owner name
            - OBJECT_NAME: Table or view name (case-sensitive, exact case as in schema)
            - OBJECT_TYPE: 'TABLE' or 'VIEW'
            - TABLESPACE_NAME: Tablespace name (for tables only)
            - NUM_ROWS: Number of rows (for tables only)
            - LAST_ANALYZED: Last analyzed date (for tables only)
            - COMMENTS: Comment text for the table or view
            """;

    private final DatabaseService databaseService;
    private final ObjectMapper objectMapper;

    public GetSchemaTool(DatabaseService databaseService) {
        this.databaseService = databaseService;
        this.objectMapper = new ObjectMapper();
    }

    @McpTool(
            name = "get_schema",
            description = DESCRIPTION
    )
    public String getSchema(
            @McpToolParam(description = "Optional schema name to filter results", required = false)
            String schemaName
    ) {
        try {
            List<Map<String, Object>> schema = databaseService.getSchemaInfo(schemaName);
            Map<String, Object> result = new LinkedHashMap<>();
            result.put("success", true);
            result.put("schema", schema);
            result.put("count", schema.size());
            return objectMapper.writerWithDefaultPrettyPrinter().writeValueAsString(result);
        } catch (Exception e) {
            try {
                Map<String, Object> result = new LinkedHashMap<>();
                result.put("success", false);
                result.put("error", e.getMessage());
                if (schemaName != null) {
                    result.put("schema_name", schemaName);
                }
                return objectMapper.writerWithDefaultPrettyPrinter().writeValueAsString(result);
            } catch (Exception jsonException) {
                String schemaStr = schemaName != null ? ",\"schema_name\":\"" + schemaName.replace("\"", "\\\"") + "\"" : "";
                return "{\"success\":false,\"error\":\"" + e.getMessage().replace("\"", "\\\"") + "\"" + schemaStr + "}";
            }
        }
    }
}

