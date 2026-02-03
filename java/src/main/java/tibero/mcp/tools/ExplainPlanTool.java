package tibero.mcp.tools;

import org.springframework.stereotype.Component;
import org.springaicommunity.mcp.annotation.McpTool;
import org.springaicommunity.mcp.annotation.McpToolParam;
import tibero.mcp.db.DatabaseService;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

@Component
public class ExplainPlanTool {

    private static final String DESCRIPTION = """
            Get execution plan for a SQL query without actually executing it.
            
            This tool analyzes the execution plan of a SQL statement (SELECT, INSERT, UPDATE, DELETE, etc.) 
            without actually executing the query. It validates whether the SQL is executable and returns 
            the execution plan in Markdown format. If the SQL is not valid, it returns an error message.
            
            Note: Table, view, and column names are case-sensitive. If they were created with 
            quoted identifiers (e.g., "atom", "Country", "Player_Attributes"), you must use 
            double quotes around the names in your SQL query to preserve case sensitivity.
            Example: EXPLAIN PLAN FOR SELECT * FROM "atom" WHERE "atom_id" = '123'
            
            Returns Markdown string with execution plan formatted as a table, including:
            - SQL ID, execution statistics
            - Execution plan tree with operations, costs, and cardinality
            - Notes and additional information
            - Error message in Markdown format if SQL is invalid or plan generation failed
            """;

    private final DatabaseService databaseService;

    public ExplainPlanTool(DatabaseService databaseService) {
        this.databaseService = databaseService;
    }

    @McpTool(
            name = "explain_plan",
            description = DESCRIPTION
    )
    public String explainPlan(
            @McpToolParam(description = "SQL query string to analyze (SELECT, INSERT, UPDATE, DELETE, etc.) (use double quotes for case-sensitive identifiers)", required = true)
            String query
    ) {
        try {
            List<Map<String, Object>> plan = databaseService.getExecutionPlan(query);
            String markdown = convertExecutionPlanToMarkdown(plan);
            return markdown;
        } catch (Exception e) {
            return "**Error generating execution plan:**\n\n```\n" + e.getMessage() + "\n```\n\n**Query:**\n```sql\n" + query + "\n```\n";
        }
    }

    private String convertExecutionPlanToMarkdown(List<Map<String, Object>> plan) {
        if (plan == null || plan.isEmpty()) {
            return "**Execution plan is empty.**\n";
        }

        StringBuilder md = new StringBuilder();
        boolean inTable = false;
        List<String> tableRows = new ArrayList<>();
        String headerLine = null;

        for (Map<String, Object> row : plan) {
            Object columnValue = row.get("COLUMN_VALUE");
            if (columnValue == null) {
                continue;
            }

            String line = columnValue.toString().trim();

            // Skip empty lines
            if (line.isEmpty()) {
                if (inTable && !tableRows.isEmpty()) {
                    // Flush table
                    md.append(buildMarkdownTable(headerLine, tableRows));
                    tableRows.clear();
                    inTable = false;
                }
                md.append("\n");
                continue;
            }

            // Check if this is a table header line (contains "|")
            if (line.contains("|") && line.contains("Operation")) {
                inTable = true;
                headerLine = line;
                tableRows.clear();
                continue;
            }

            // Check if this is a separator line
            if (inTable && line.matches("^[-|]+$")) {
                continue;
            }

            // Check if this is a table data row
            if (inTable && line.contains("|") && !line.matches("^[-|]+$")) {
                tableRows.add(line);
                continue;
            }

            // If we were in a table and hit a non-table line, flush the table
            if (inTable && !line.contains("|")) {
                md.append(buildMarkdownTable(headerLine, tableRows));
                tableRows.clear();
                inTable = false;
            }

            // Regular text line
            if (line.startsWith("Note") || line.startsWith("---")) {
                md.append(line).append("\n");
            } else if (line.contains("SQL") && line.contains(":")) {
                // SQL section - format as code block
                md.append("**").append(line).append("**\n\n");
            } else if (line.length() > 0 && !line.matches("^\\s*$")) {
                md.append(line).append("\n");
            }
        }

        // Flush any remaining table
        if (inTable && !tableRows.isEmpty()) {
            md.append(buildMarkdownTable(headerLine, tableRows));
        }

        return md.toString();
    }

    private String buildMarkdownTable(String headerLine, List<String> dataRows) {
        if (headerLine == null || dataRows.isEmpty()) {
            return "";
        }

        StringBuilder table = new StringBuilder();

        // Parse header and build markdown header
        String[] headerCells = parseTableRow(headerLine);
        table.append("| ").append(String.join(" | ", headerCells)).append(" |\n");

        // Build separator
        table.append("|");
        for (int i = 0; i < headerCells.length; i++) {
            table.append("---|");
        }
        table.append("\n");

        // Add data rows
        for (String row : dataRows) {
            String[] cells = parseTableRow(row);
            table.append("| ").append(String.join(" | ", cells)).append(" |\n");
        }

        table.append("\n");
        return table.toString();
    }

    private String[] parseTableRow(String row) {
        // Remove leading/trailing spaces and split by |
        String cleaned = row.trim();
        if (cleaned.startsWith("|")) {
            cleaned = cleaned.substring(1);
        }
        if (cleaned.endsWith("|")) {
            cleaned = cleaned.substring(0, cleaned.length() - 1);
        }
        String[] parts = cleaned.split("\\|");
        String[] cells = new String[parts.length];
        for (int i = 0; i < parts.length; i++) {
            cells[i] = parts[i].trim();
        }
        return cells;
    }
}

