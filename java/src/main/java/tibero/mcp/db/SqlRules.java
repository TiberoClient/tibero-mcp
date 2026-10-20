package tibero.mcp.db;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import tibero.mcp.ToolException;

/**
 * Statement checks and identifier helpers. Mirrors python/src/db/query_executor.py;
 * both are tested against spec/conformance/cases.json.
 */
public final class SqlRules {

    private static final Pattern LEADING_NOISE = Pattern.compile("^(\\s+|--[^\\n]*\\n?|/\\*.*?\\*/|\\()+",
            Pattern.DOTALL | Pattern.UNICODE_CHARACTER_CLASS);

    private static final Pattern WORD = Pattern.compile("^[A-Za-z]+");

    private static final Set<String> SELECT_KEYWORDS = Set.of("SELECT", "WITH");

    private static final Set<String> DML_KEYWORDS = Set.of("INSERT", "UPDATE", "DELETE", "MERGE");

    private SqlRules() {
    }

    /** Strip whitespace and trailing semicolons, which the JDBC driver rejects. */
    public static String normalizeStatement(String query) {
        String statement = query == null ? "" : query.strip();
        while (statement.endsWith(";")) {
            statement = statement.substring(0, statement.length() - 1).stripTrailing();
        }
        if (statement.isEmpty()) {
            throw new ToolException("SQL statement is empty.");
        }
        return statement;
    }

    /** First SQL keyword, skipping comments and opening parentheses. */
    public static String leadingKeyword(String statement) {
        String body = LEADING_NOISE.matcher(statement).replaceFirst("");
        Matcher match = WORD.matcher(body);
        return match.find() ? match.group().toUpperCase(Locale.ROOT) : "";
    }

    public static void ensureSelect(String statement) {
        if (!SELECT_KEYWORDS.contains(leadingKeyword(statement))) {
            throw new ToolException(
                    "Only SELECT (or WITH ... SELECT) statements are allowed here. Use execute_dml for INSERT/UPDATE/DELETE/MERGE.");
        }
    }

    public static void ensureDml(String statement) {
        if (!DML_KEYWORDS.contains(leadingKeyword(statement))) {
            throw new ToolException(
                    "Only INSERT, UPDATE, DELETE or MERGE statements are allowed. DDL and other statements are rejected.");
        }
    }

    /** Quote an identifier exactly as stored in the dictionary. */
    public static String quoteIdentifier(String name) {
        return "\"" + name.replace("\"", "\"\"") + "\"";
    }

    /** Make column labels unique (ID, ID_2, ...) so rows keyed by label lose no column. */
    public static List<String> uniqueLabels(List<String> labels) {
        Set<String> used = new HashSet<>();
        List<String> result = new ArrayList<>();
        for (String label : labels) {
            String name = label;
            int suffix = 1;
            while (used.contains(name)) {
                suffix++;
                name = label + "_" + suffix;
            }
            used.add(name);
            result.add(name);
        }
        return result;
    }
}
