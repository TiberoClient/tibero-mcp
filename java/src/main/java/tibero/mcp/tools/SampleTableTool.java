package tibero.mcp.tools;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Component;
import org.springaicommunity.mcp.annotation.McpTool;
import org.springaicommunity.mcp.annotation.McpToolParam;
import tibero.mcp.db.DatabaseService;

import java.util.*;

@Component
public class SampleTableTool {

    private static final String DESCRIPTION = """
            Sample n rows from a specific table.
            
            This tool retrieves a sample of rows from a table without loading all data. 
            It's useful for quickly inspecting table contents and structure.
            
            Note: Table names are case-sensitive. If the table name was created with quoted 
            identifiers (e.g., "atom", "Country", "Player_Attributes"), you must use the exact 
            case as defined in the schema. Use double quotes around the name if it contains 
            mixed case or special characters.
            
            Returns JSON string with sample result containing:
            - success: Whether the sampling was successful
            - schema_name: Schema name
            - table_name: Table name
            - rows: Array of sampled rows (each row is a dictionary with column names as keys)
            - row_count: Number of rows returned
            - limit: Requested limit
            - error: Error message if sampling failed
            """;

    private final DatabaseService databaseService;
    private final ObjectMapper objectMapper;

    public SampleTableTool(DatabaseService databaseService) {
        this.databaseService = databaseService;
        this.objectMapper = new ObjectMapper();
    }

    @McpTool(
            name = "sample_table",
            description = DESCRIPTION
    )
    public String sampleTable(
            @McpToolParam(description = "Schema name (owner) of the table", required = true)
            String schemaName,
            @McpToolParam(description = "Name of the table to sample (case-sensitive, use exact case as in schema)", required = true)
            String tableName,
            @McpToolParam(description = "Number of rows to sample (default: 10, maximum: 1000)", required = false)
            Integer limit
    ) {
        try {
            int actualLimit = limit != null ? limit : 10;
            List<Map<String, Object>> rows = databaseService.sampleTableRows(schemaName, tableName, actualLimit);
            Map<String, Object> result = new LinkedHashMap<>();
            result.put("success", true);
            result.put("schema_name", schemaName);
            result.put("table_name", tableName);
            result.put("rows", rows);
            result.put("row_count", rows.size());
            result.put("limit", actualLimit);
            result.put("error", null);
            return objectMapper.writerWithDefaultPrettyPrinter().writeValueAsString(result);
        } catch (Exception e) {
            try {
                Map<String, Object> result = new LinkedHashMap<>();
                result.put("success", false);
                result.put("error", e.getMessage());
                result.put("schema_name", schemaName);
                result.put("table_name", tableName);
                if (limit != null) {
                    result.put("limit", limit);
                }
                return objectMapper.writerWithDefaultPrettyPrinter().writeValueAsString(result);
            } catch (Exception jsonException) {
                String limitStr = limit != null ? ",\"limit\":" + limit : "";
                return "{\"success\":false,\"error\":\"" + e.getMessage().replace("\"", "\\\"") + "\",\"schema_name\":\"" + schemaName.replace("\"", "\\\"") + "\",\"table_name\":\"" + tableName.replace("\"", "\\\"") + "\"" + limitStr + "}";
            }
        }
    }
}

