package tibero.mcp.tools;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Component;
import org.springaicommunity.mcp.annotation.McpTool;
import org.springaicommunity.mcp.annotation.McpToolParam;
import tibero.mcp.db.DatabaseService;

import java.util.*;

@Component
public class ExecuteDmlTool {

    private static final String DESCRIPTION = """
            Execute a DML statement (INSERT, UPDATE, DELETE) on the Tibero database.
            
            **IMPORTANT: Before executing a DML statement, it is strongly recommended to first use 
            the explain_plan tool to validate the SQL syntax and verify that the statement matches 
            your intended logic. This helps catch errors and prevent unintended data modifications 
            before actual execution.**
            
            This tool is specifically designed for Data Manipulation Language statements 
            and returns the number of affected rows. The transaction is automatically 
            committed on success (unless auto_commit is False) and rolled back on error.
            
            Note: Table, view, and column names are case-sensitive. If they were created with 
            quoted identifiers (e.g., "atom", "Country", "Player_Attributes"), you must use 
            double quotes around the names in your SQL statement to preserve case sensitivity.
            Example: INSERT INTO "atom" ("atom_id", "molecule_id") VALUES ('123', '456')
            
            Returns JSON string with execution result containing:
            - success: Whether the DML statement executed successfully
            - rowcount: Number of rows affected by the statement
            """;

    private final DatabaseService databaseService;
    private final ObjectMapper objectMapper;

    public ExecuteDmlTool(DatabaseService databaseService) {
        this.databaseService = databaseService;
        this.objectMapper = new ObjectMapper();
    }

    @McpTool(
            name = "execute_dml",
            description = DESCRIPTION
    )
    public String executeDml(
            @McpToolParam(description = "DML statement to execute (INSERT, UPDATE, DELETE) (use double quotes for case-sensitive identifiers)", required = true)
            String query,
            @McpToolParam(description = "Whether to automatically commit the transaction (default: True)", required = false)
            Boolean autoCommit
    ) {
        try {
            boolean autoCommitValue = autoCommit != null ? autoCommit : true;
            int rowCount = databaseService.executeDml(query, autoCommitValue);
            Map<String, Object> result = new LinkedHashMap<>();
            result.put("success", true);
            result.put("rowcount", rowCount);
            return objectMapper.writerWithDefaultPrettyPrinter().writeValueAsString(result);
        } catch (Exception e) {
            try {
                Map<String, Object> result = new LinkedHashMap<>();
                result.put("success", false);
                result.put("error", e.getMessage());
                result.put("query", query);
                if (autoCommit != null) {
                    result.put("auto_commit", autoCommit);
                }
                return objectMapper.writerWithDefaultPrettyPrinter().writeValueAsString(result);
            } catch (Exception jsonException) {
                String autoCommitStr = autoCommit != null ? ",\"auto_commit\":" + autoCommit : "";
                return "{\"success\":false,\"error\":\"" + e.getMessage().replace("\"", "\\\"") + "\",\"query\":\"" + query.replace("\"", "\\\"").replace("\n", "\\n").replace("\r", "\\r") + "\"" + autoCommitStr + "}";
            }
        }
    }
}

