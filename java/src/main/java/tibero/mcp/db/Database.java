package tibero.mcp.db;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.ResultSetMetaData;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

import javax.sql.DataSource;

import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;

import tibero.mcp.Config;

/**
 * Tibero access. Each method mirrors a function in python/src/db (same SQL, same
 * transaction handling, same row shape) so both servers answer identically.
 */
public class Database implements AutoCloseable {

    /** One page of rows plus whether more existed. */
    public record Page(List<String> columns, List<Map<String, Object>> rows, boolean truncated) {
    }

    private static final String DEFAULT_SYSTEM_SCHEMAS = "SYS,SYSCAT,SYSGIS,SYSBACKUP,LBACSYS,OUTLN,PUBLIC,TIBERO,TIBERO1";

    private static final String OBJECTS_QUERY = """
            SELECT
                t.OWNER AS SCHEMA_NAME,
                t.TABLE_NAME AS OBJECT_NAME,
                'TABLE' AS OBJECT_TYPE,
                t.NUM_ROWS,
                t.LAST_ANALYZED,
                tc.COMMENTS
            FROM ALL_TABLES t
            LEFT JOIN ALL_TAB_COMMENTS tc
                ON t.OWNER = tc.OWNER
                AND t.TABLE_NAME = tc.TABLE_NAME
            WHERE %s

            UNION ALL

            SELECT
                v.OWNER AS SCHEMA_NAME,
                v.VIEW_NAME AS OBJECT_NAME,
                'VIEW' AS OBJECT_TYPE,
                NULL AS NUM_ROWS,
                NULL AS LAST_ANALYZED,
                vc.COMMENTS
            FROM ALL_VIEWS v
            LEFT JOIN ALL_TAB_COMMENTS vc
                ON v.OWNER = vc.OWNER
                AND v.VIEW_NAME = vc.TABLE_NAME
            WHERE %s

            ORDER BY 1, 3, 2
            """;

    private final DataSource dataSource;

    private final int queryTimeoutSeconds;

    private final JsonValues values;

    private final List<String> systemSchemas;

    public Database(DataSource dataSource, int queryTimeoutSeconds, int maxCellChars, List<String> systemSchemas) {
        this.dataSource = dataSource;
        this.queryTimeoutSeconds = queryTimeoutSeconds;
        this.values = new JsonValues(maxCellChars);
        this.systemSchemas = systemSchemas.stream().map(s -> s.toUpperCase(Locale.ROOT)).toList();
    }

    public static Database fromConfig(Config config) {
        HikariConfig pool = new HikariConfig();
        pool.setJdbcUrl(String.format("jdbc:tibero:thin:@%s:%s:%s", config.get("TIBERO_HOST", "localhost"),
                config.get("TIBERO_PORT", "8629"), config.get("TIBERO_DATABASE", "tibero")));
        pool.setUsername(config.get("TIBERO_USER"));
        pool.setPassword(config.get("TIBERO_PASSWORD"));
        pool.setDriverClassName("com.tmax.tibero.jdbc.TbDriver");
        pool.setMaximumPoolSize(10);
        pool.setMinimumIdle(0);
        // Start without touching the database, like the Python server: tools/list and
        // the health check must work while the DB is down.
        pool.setInitializationFailTimeout(-1);
        pool.setConnectionTimeout(30_000);
        pool.setPoolName("tibero-mcp");
        List<String> system = Config.of(Map.of("V", config.get("TIBERO_SYSTEM_SCHEMAS", DEFAULT_SYSTEM_SCHEMAS)))
            .list("V");
        return new Database(new HikariDataSource(pool), config.getInt("TIBERO_QUERY_TIMEOUT", 60),
                config.getInt("TIBERO_MAX_CELL_CHARS", 4000), system);
    }

    public JsonValues values() {
        return values;
    }

    // ----- statements -----

    public Page runSelect(String query, int maxRows) throws SQLException {
        String statement = SqlRules.normalizeStatement(query);
        SqlRules.ensureSelect(statement);
        try (Connection conn = dataSource.getConnection();
                PreparedStatement stmt = prepare(conn, statement, maxRows + 1)) {
            try (ResultSet rs = stmt.executeQuery()) {
                Page page = fetch(rs, maxRows + 1);
                boolean truncated = page.rows().size() > maxRows;
                List<Map<String, Object>> rows = truncated ? page.rows().subList(0, maxRows) : page.rows();
                return new Page(page.columns(), new ArrayList<>(rows), truncated);
            }
        }
    }

    /** Executes one DML statement and commits, or rolls back when {@code dryRun}. */
    public long executeDml(String query, boolean dryRun) throws SQLException {
        String statement = SqlRules.normalizeStatement(query);
        SqlRules.ensureDml(statement);
        try (Connection conn = dataSource.getConnection()) {
            conn.setAutoCommit(false);
            try (PreparedStatement stmt = prepare(conn, statement, 0)) {
                long rowcount = stmt.executeLargeUpdate();
                if (dryRun) {
                    conn.rollback();
                }
                else {
                    conn.commit();
                }
                return rowcount;
            }
            catch (SQLException | RuntimeException e) {
                conn.rollback();
                throw e;
            }
        }
    }

    /**
     * Tibero has no DBMS_XPLAN: EXPLAIN PLAN writes PLAN_TABLE, which is read in the
     * same uncommitted transaction and rolled back so concurrent plans never mix.
     */
    public List<Map<String, Object>> explainPlan(String query) throws SQLException {
        String statement = SqlRules.normalizeStatement(query);
        try (Connection conn = dataSource.getConnection()) {
            conn.setAutoCommit(false);
            try {
                try (PreparedStatement explain = prepare(conn, "EXPLAIN PLAN FOR " + statement, 0)) {
                    explain.execute();
                }
                return select(conn, """
                        SELECT ID, PARENT_ID, DEPTH, OPERATION, OBJECT_OWNER, OBJECT_NAME,
                               COST, CARDINALITY, ACCESS_PREDICATES, FILTER_PREDICATES
                        FROM PLAN_TABLE
                        ORDER BY ID
                        """, List.of());
            }
            finally {
                conn.rollback();
            }
        }
    }

    public List<Map<String, Object>> sampleTableRows(String schemaName, String tableName, int limit)
            throws SQLException {
        int actual = Math.max(1, Math.min(limit, 1000));
        String query = "SELECT * FROM " + SqlRules.quoteIdentifier(schemaName) + "."
                + SqlRules.quoteIdentifier(tableName) + " WHERE ROWNUM <= " + actual;
        try (Connection conn = dataSource.getConnection(); PreparedStatement stmt = prepare(conn, query, actual)) {
            try (ResultSet rs = stmt.executeQuery()) {
                return fetch(rs, actual).rows();
            }
        }
    }

    // ----- dictionary -----

    public List<Map<String, Object>> getSchemaInfo(String schemaName) throws SQLException {
        if (schemaName != null) {
            return select(OBJECTS_QUERY.formatted("t.OWNER = UPPER(?)", "v.OWNER = UPPER(?)"),
                    List.of(schemaName, schemaName));
        }
        String placeholders = String.join(", ", systemSchemas.stream().map(s -> "?").toList());
        List<Object> params = new ArrayList<>(systemSchemas);
        params.addAll(systemSchemas);
        return select(OBJECTS_QUERY.formatted("t.OWNER NOT IN (" + placeholders + ")",
                "v.OWNER NOT IN (" + placeholders + ")"), params);
    }

    /** Exact name first, then upper-case (unquoted identifiers are stored upper-case). */
    public Map<String, Object> resolveObject(String schemaName, String tableName) throws SQLException {
        String query = """
                SELECT o.OWNER, o.OBJECT_NAME, o.OBJECT_TYPE, c.COMMENTS
                FROM ALL_OBJECTS o
                LEFT JOIN ALL_TAB_COMMENTS c
                    ON o.OWNER = c.OWNER AND o.OBJECT_NAME = c.TABLE_NAME
                WHERE o.OWNER = UPPER(?)
                  AND o.OBJECT_NAME = ?
                  AND o.OBJECT_TYPE IN ('TABLE', 'VIEW')
                """;
        for (String candidate : new java.util.LinkedHashSet<>(List.of(tableName, tableName.toUpperCase(Locale.ROOT)))) {
            List<Map<String, Object>> rows = select(query, List.of(schemaName, candidate));
            if (!rows.isEmpty()) {
                return rows.get(0);
            }
        }
        return null;
    }

    public List<Map<String, Object>> getTableColumns(String schemaName, String tableName) throws SQLException {
        return select("""
                SELECT
                    c.COLUMN_NAME,
                    c.DATA_TYPE,
                    c.DATA_LENGTH,
                    c.DATA_PRECISION,
                    c.DATA_SCALE,
                    c.NULLABLE,
                    c.DATA_DEFAULT,
                    c.COLUMN_ID,
                    cc.COMMENTS
                FROM ALL_TAB_COLUMNS c
                LEFT JOIN ALL_COL_COMMENTS cc
                    ON c.OWNER = cc.OWNER
                    AND c.TABLE_NAME = cc.TABLE_NAME
                    AND c.COLUMN_NAME = cc.COLUMN_NAME
                WHERE c.OWNER = ?
                  AND c.TABLE_NAME = ?
                ORDER BY c.COLUMN_ID
                """, List.of(schemaName, tableName));
    }

    /** Constraints with their columns and, for foreign keys, the referenced table and columns. */
    public List<Map<String, Object>> getTableConstraints(String schemaName, String tableName) throws SQLException {
        List<Map<String, Object>> rows = select("""
                SELECT
                    c.CONSTRAINT_NAME,
                    c.CONSTRAINT_TYPE,
                    c.SEARCH_CONDITION,
                    c.STATUS,
                    cc.COLUMN_NAME,
                    cc.POSITION,
                    r.OWNER AS R_OWNER,
                    r.TABLE_NAME AS R_TABLE_NAME,
                    rc.COLUMN_NAME AS R_COLUMN_NAME
                FROM ALL_CONSTRAINTS c
                LEFT JOIN ALL_CONS_COLUMNS cc
                    ON c.OWNER = cc.OWNER AND c.CONSTRAINT_NAME = cc.CONSTRAINT_NAME
                LEFT JOIN ALL_CONSTRAINTS r
                    ON c.R_OWNER = r.OWNER AND c.R_CONSTRAINT_NAME = r.CONSTRAINT_NAME
                LEFT JOIN ALL_CONS_COLUMNS rc
                    ON r.OWNER = rc.OWNER AND r.CONSTRAINT_NAME = rc.CONSTRAINT_NAME AND rc.POSITION = cc.POSITION
                WHERE c.OWNER = ?
                  AND c.TABLE_NAME = ?
                ORDER BY c.CONSTRAINT_NAME, cc.POSITION
                """, List.of(schemaName, tableName));
        Map<Object, Map<String, Object>> constraints = new LinkedHashMap<>();
        for (Map<String, Object> row : rows) {
            Map<String, Object> entry = constraints.computeIfAbsent(row.get("CONSTRAINT_NAME"), name -> {
                Map<String, Object> created = new LinkedHashMap<>();
                created.put("CONSTRAINT_NAME", row.get("CONSTRAINT_NAME"));
                created.put("CONSTRAINT_TYPE", row.get("CONSTRAINT_TYPE"));
                created.put("SEARCH_CONDITION", row.get("SEARCH_CONDITION"));
                created.put("STATUS", row.get("STATUS"));
                created.put("COLUMNS", new ArrayList<>());
                return created;
            });
            if (row.get("COLUMN_NAME") != null) {
                columnsOf(entry).add(row.get("COLUMN_NAME"));
            }
            if (row.get("R_TABLE_NAME") != null) {
                @SuppressWarnings("unchecked")
                Map<String, Object> ref = (Map<String, Object>) entry.computeIfAbsent("REFERENCES", key -> {
                    Map<String, Object> created = new LinkedHashMap<>();
                    created.put("OWNER", row.get("R_OWNER"));
                    created.put("TABLE_NAME", row.get("R_TABLE_NAME"));
                    created.put("COLUMNS", new ArrayList<>());
                    return created;
                });
                if (row.get("R_COLUMN_NAME") != null) {
                    columnsOf(ref).add(row.get("R_COLUMN_NAME"));
                }
            }
        }
        return new ArrayList<>(constraints.values());
    }

    /** Indexes with their columns in key order. */
    public List<Map<String, Object>> getTableIndexes(String schemaName, String tableName) throws SQLException {
        List<Map<String, Object>> rows = select("""
                SELECT
                    i.INDEX_NAME,
                    i.INDEX_TYPE,
                    i.UNIQUENESS,
                    i.STATUS,
                    ic.COLUMN_NAME,
                    ic.COLUMN_POSITION
                FROM ALL_INDEXES i
                LEFT JOIN ALL_IND_COLUMNS ic
                    ON i.OWNER = ic.INDEX_OWNER AND i.INDEX_NAME = ic.INDEX_NAME
                WHERE i.TABLE_OWNER = ?
                  AND i.TABLE_NAME = ?
                ORDER BY i.INDEX_NAME, ic.COLUMN_POSITION
                """, List.of(schemaName, tableName));
        Map<Object, Map<String, Object>> indexes = new LinkedHashMap<>();
        for (Map<String, Object> row : rows) {
            Map<String, Object> entry = indexes.computeIfAbsent(row.get("INDEX_NAME"), name -> {
                Map<String, Object> created = new LinkedHashMap<>();
                created.put("INDEX_NAME", row.get("INDEX_NAME"));
                created.put("INDEX_TYPE", row.get("INDEX_TYPE"));
                created.put("UNIQUENESS", row.get("UNIQUENESS"));
                created.put("STATUS", row.get("STATUS"));
                created.put("COLUMNS", new ArrayList<>());
                return created;
            });
            if (row.get("COLUMN_NAME") != null) {
                columnsOf(entry).add(row.get("COLUMN_NAME"));
            }
        }
        return new ArrayList<>(indexes.values());
    }

    // ----- plumbing -----

    @SuppressWarnings("unchecked")
    private static List<Object> columnsOf(Map<String, Object> entry) {
        return (List<Object>) entry.get("COLUMNS");
    }

    private PreparedStatement prepare(Connection conn, String sql, int maxRows) throws SQLException {
        PreparedStatement stmt = conn.prepareStatement(sql);
        stmt.setQueryTimeout(queryTimeoutSeconds);
        if (maxRows > 0) {
            stmt.setMaxRows(maxRows);
        }
        return stmt;
    }

    private List<Map<String, Object>> select(String sql, List<Object> params) throws SQLException {
        try (Connection conn = dataSource.getConnection()) {
            return select(conn, sql, params);
        }
    }

    private List<Map<String, Object>> select(Connection conn, String sql, List<Object> params) throws SQLException {
        try (PreparedStatement stmt = prepare(conn, sql, 0)) {
            for (int i = 0; i < params.size(); i++) {
                stmt.setObject(i + 1, params.get(i));
            }
            try (ResultSet rs = stmt.executeQuery()) {
                return fetch(rs, Integer.MAX_VALUE).rows();
            }
        }
    }

    private Page fetch(ResultSet rs, int limit) throws SQLException {
        ResultSetMetaData meta = rs.getMetaData();
        int count = meta.getColumnCount();
        List<String> labels = new ArrayList<>();
        int[] types = new int[count];
        for (int i = 1; i <= count; i++) {
            labels.add(meta.getColumnLabel(i));
            types[i - 1] = meta.getColumnType(i);
        }
        List<String> columns = SqlRules.uniqueLabels(labels);
        List<Map<String, Object>> rows = new ArrayList<>();
        while (rows.size() < limit && rs.next()) {
            Map<String, Object> row = new LinkedHashMap<>();
            for (int i = 0; i < count; i++) {
                row.put(columns.get(i), values.read(rs, i + 1, types[i]));
            }
            rows.add(row);
        }
        return new Page(columns, rows, false);
    }

    @Override
    public void close() {
        if (dataSource instanceof HikariDataSource hikari) {
            hikari.close();
        }
    }
}
