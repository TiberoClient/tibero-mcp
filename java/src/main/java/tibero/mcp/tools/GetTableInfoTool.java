package tibero.mcp.tools;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Component;
import org.springaicommunity.mcp.annotation.McpTool;
import org.springaicommunity.mcp.annotation.McpToolParam;
import tibero.mcp.db.DatabaseService;

import java.util.*;

@Component
public class GetTableInfoTool {

    private static final String DESCRIPTION = """
            Get detailed information about a specific table or view.
            
            This tool works for both tables and views. For views, constraints and indexes 
            will typically be empty arrays.
            
            Note: Table and view names are case-sensitive. If the table/view name was created 
            with quoted identifiers (e.g., "atom", "Country", "Player_Attributes"), you must 
            use the exact case as defined in the schema. Use double quotes around the name 
            if it contains mixed case or special characters.
            
            Returns JSON string with table/view details containing:
            - success: Whether the operation was successful
            - schema_name: Schema name
            - table_name: Table or view name
            - columns: Array of column information (including COMMENTS for each column)
            - constraints: Array of constraint information (empty for views)
            - indexes: Array of index information (empty for views)
            - error: Error message if operation failed
            """;

    private final DatabaseService databaseService;
    private final ObjectMapper objectMapper;

    public GetTableInfoTool(DatabaseService databaseService) {
        this.databaseService = databaseService;
        this.objectMapper = new ObjectMapper();
    }

    @McpTool(
            name = "get_table_info",
            description = DESCRIPTION
    )
    public String getTableInfo(
            @McpToolParam(description = "Schema name", required = true)
            String schemaName,
            @McpToolParam(description = "Table or view name (case-sensitive, use exact case as in schema)", required = true)
            String tableName
    ) {
        try {
            List<Map<String, Object>> columns = databaseService.getTableColumns(schemaName, tableName);
            List<Map<String, Object>> constraints = databaseService.getTableConstraints(schemaName, tableName);
            List<Map<String, Object>> indexes = databaseService.getTableIndexes(schemaName, tableName);
            
            Map<String, Object> result = new LinkedHashMap<>();
            result.put("success", true);
            result.put("schema_name", schemaName);
            result.put("table_name", tableName);
            result.put("columns", columns);
            result.put("constraints", constraints);
            result.put("indexes", indexes);
            return objectMapper.writerWithDefaultPrettyPrinter().writeValueAsString(result);
        } catch (Exception e) {
            try {
                Map<String, Object> result = new LinkedHashMap<>();
                result.put("success", false);
                result.put("error", e.getMessage());
                result.put("schema_name", schemaName);
                result.put("table_name", tableName);
                return objectMapper.writerWithDefaultPrettyPrinter().writeValueAsString(result);
            } catch (Exception jsonException) {
                return "{\"success\":false,\"error\":\"" + e.getMessage().replace("\"", "\\\"") + "\",\"schema_name\":\"" + schemaName.replace("\"", "\\\"") + "\",\"table_name\":\"" + tableName.replace("\"", "\\\"") + "\"}";
            }
        }
    }
}

