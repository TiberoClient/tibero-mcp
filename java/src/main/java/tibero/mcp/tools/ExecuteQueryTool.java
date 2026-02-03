package tibero.mcp.tools;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Component;
import org.springaicommunity.mcp.annotation.McpTool;
import org.springaicommunity.mcp.annotation.McpToolParam;
import tibero.mcp.db.DatabaseService;

import java.util.*;

@Component
public class ExecuteQueryTool {

    private static final String DESCRIPTION = """
            Execute a SELECT query on the Tibero database and return results.
            
            **IMPORTANT: Before executing a query, it is strongly recommended to first use the 
            explain_plan tool to validate the SQL syntax and verify that the query matches your 
            intended logic. This helps catch errors and semantic issues before actual execution.**
            
            This tool is designed for SELECT queries that return result sets. 
            It executes the query and returns all rows in JSONL format (one JSON object per line).
            
            Note: Table, view, and column names are case-sensitive. If they were created with 
            quoted identifiers (e.g., "atom", "Country", "Player_Attributes"), you must use 
            double quotes around the names in your SQL query to preserve case sensitivity.
            Example: SELECT * FROM "atom" WHERE "atom_id" = '123'
            
            Returns JSONL string where:
            - First line contains metadata: {"success": true, "row_count": N}
            - Subsequent lines contain data rows (each row is a dictionary with column names as keys)
            - Rows are separated by newline characters
            - On error, returns a single line with success: false, error message, and row_count: 0
            """;

    private final DatabaseService databaseService;
    private final ObjectMapper objectMapper;

    public ExecuteQueryTool(DatabaseService databaseService) {
        this.databaseService = databaseService;
        this.objectMapper = new ObjectMapper();
    }

    @McpTool(
            name = "execute_query_jsonl",
            description = DESCRIPTION
    )
    public String executeQuery(
            @McpToolParam(description = "SELECT SQL query to execute (use double quotes for case-sensitive identifiers)", required = true)
            String query
    ) {
        try {
            List<Map<String, Object>> results = databaseService.executeSelectQuery(query);
            StringBuilder jsonl = new StringBuilder();
            
            // First line: metadata with success and row_count
            Map<String, Object> metadata = new LinkedHashMap<>();
            metadata.put("success", true);
            metadata.put("row_count", results.size());
            jsonl.append(objectMapper.writeValueAsString(metadata));
            jsonl.append("\n");
            
            // Write each row as a separate JSON object (JSONL format)
            for (Map<String, Object> row : results) {
                jsonl.append(objectMapper.writeValueAsString(row));
                jsonl.append("\n");
            }
            
            return jsonl.toString();
        } catch (Exception e) {
            try {
                // On error, return error info as JSONL
                Map<String, Object> errorRow = new LinkedHashMap<>();
                errorRow.put("success", false);
                errorRow.put("error", e.getMessage());
                errorRow.put("query", query);
                return objectMapper.writeValueAsString(errorRow) + "\n";
            } catch (Exception jsonException) {
                return "{\"success\":false,\"error\":\"" + e.getMessage().replace("\"", "\\\"") + "\",\"query\":\"" + query.replace("\"", "\\\"").replace("\n", "\\n").replace("\r", "\\r") + "\"}\n";
            }
        }
    }
}

