package tibero.mcp.tools;

import org.springframework.stereotype.Component;
import org.springaicommunity.mcp.annotation.McpTool;
import org.springaicommunity.mcp.annotation.McpToolParam;
import tibero.mcp.db.DatabaseService;

import java.util.*;

@Component
public class ExecuteQueryMdTool {

    private static final String DESCRIPTION = """
            Execute a SELECT query on the Tibero database and return results as a Markdown table.
            
            **IMPORTANT: Before executing a query, it is strongly recommended to first use the 
            explain_plan tool to validate the SQL syntax and verify that the query matches your 
            intended logic. This helps catch errors and semantic issues before actual execution.**
            
            This tool is designed for SELECT queries that return result sets. 
            It executes the query and returns all rows as a Markdown-formatted table.
            
            Note: Table, view, and column names are case-sensitive. If they were created with 
            quoted identifiers (e.g., "atom", "Country", "Player_Attributes"), you must use 
            double quotes around the names in your SQL query to preserve case sensitivity.
            Example: SELECT * FROM "atom" WHERE "atom_id" = '123'
            
            Returns Markdown table string with:
            - Header row with column names
            - Separator row
            - Data rows with values
            - On error, returns error message in Markdown format
            """;

    private final DatabaseService databaseService;

    public ExecuteQueryMdTool(DatabaseService databaseService) {
        this.databaseService = databaseService;
    }

    @McpTool(
            name = "execute_query_md",
            description = DESCRIPTION
    )
    public String executeQueryMd(
            @McpToolParam(description = "SELECT SQL query to execute (use double quotes for case-sensitive identifiers)", required = true)
            String query
    ) {
        try {
            List<Map<String, Object>> results = databaseService.executeSelectQuery(query);
            
            if (results.isEmpty()) {
                return "**Query executed successfully.**\n\n*No rows returned.*\n";
            }
            
            // Get column names from first row
            Set<String> columns = new LinkedHashSet<>(results.get(0).keySet());
            List<String> columnList = new ArrayList<>(columns);
            
            StringBuilder md = new StringBuilder();
            
            // Build header row
            md.append("| ");
            for (String col : columnList) {
                md.append(escapeMarkdown(col)).append(" | ");
            }
            md.append("\n");
            
            // Build separator row
            md.append("|");
            for (int i = 0; i < columnList.size(); i++) {
                md.append("---|");
            }
            md.append("\n");
            
            // Build data rows
            for (Map<String, Object> row : results) {
                md.append("| ");
                for (String col : columnList) {
                    Object value = row.get(col);
                    String cellValue = value == null ? "" : escapeMarkdown(String.valueOf(value));
                    md.append(cellValue).append(" | ");
                }
                md.append("\n");
            }
            
            return md.toString();
        } catch (Exception e) {
            return "**Error executing query:**\n\n```\n" + e.getMessage() + "\n```\n";
        }
    }
    
    private String escapeMarkdown(String text) {
        if (text == null) {
            return "";
        }
        // Escape pipe characters and newlines for Markdown table
        return text.replace("|", "\\|")
                  .replace("\n", " ")
                  .replace("\r", " ");
    }
}

