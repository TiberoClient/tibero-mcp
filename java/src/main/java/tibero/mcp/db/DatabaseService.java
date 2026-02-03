package tibero.mcp.db;

import org.springframework.stereotype.Service;

import javax.sql.DataSource;
import java.sql.*;
import java.util.*;

@Service
public class DatabaseService {

    private final DataSource dataSource;

    public DatabaseService(DataSource dataSource) {
        this.dataSource = dataSource;
    }

    public List<Map<String, Object>> executeSelectQuery(String query) throws SQLException {
        try (Connection conn = dataSource.getConnection();
            Statement stmt = conn.createStatement()) {
            
            try (ResultSet rs = stmt.executeQuery(query)) {
                return resultSetToList(rs);
            }
        }
    }

    public int executeDml(String query, boolean autoCommit) throws SQLException {
        try (Connection conn = dataSource.getConnection()) {
            boolean originalAutoCommit = conn.getAutoCommit();
            try {
                conn.setAutoCommit(false);
                try (Statement stmt = conn.createStatement()) {
                    stmt.executeUpdate(query);
                    int rowCount = stmt.getUpdateCount();
                    if (autoCommit) {
                        conn.commit();
                    }
                    return rowCount;
                } catch (SQLException e) {
                    conn.rollback();
                    throw e;
                }
            } finally {
                conn.setAutoCommit(originalAutoCommit);
            }
        }
    }

    public List<Map<String, Object>> getExecutionPlan(String query) throws SQLException {
        try (Connection conn = dataSource.getConnection();
            Statement stmt = conn.createStatement()) {
            
            stmt.execute("EXPLAIN PLAN FOR " + query);
            
            try (ResultSet rs = stmt.executeQuery(
                    "SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY)")) {
                return resultSetToList(rs);
            }
        }
    }


    public List<Map<String, Object>> sampleTableRows(String schemaName, String tableName, int limit) throws SQLException {
        int actualLimit = Math.max(1, Math.min(1000, limit));
        String qualifiedTable = "\"" + schemaName + "\".\"" + tableName + "\"";
        String query = "SELECT * FROM " + qualifiedTable + " WHERE ROWNUM <= " + actualLimit;
        
        try (Connection conn = dataSource.getConnection();
            Statement stmt = conn.createStatement()) {
            try (ResultSet rs = stmt.executeQuery(query)) {
                return resultSetToList(rs);
            }
        }
    }

    public List<Map<String, Object>> getSchemaInfo(String schemaName) throws SQLException {
        String query = schemaName != null ? """
            SELECT t.OWNER as SCHEMA_NAME, t.TABLE_NAME as OBJECT_NAME, 'TABLE' as OBJECT_TYPE,
                   t.TABLESPACE_NAME, t.NUM_ROWS, t.LAST_ANALYZED, tc.COMMENTS
            FROM ALL_TABLES t
            LEFT JOIN ALL_TAB_COMMENTS tc ON t.OWNER = tc.OWNER AND t.TABLE_NAME = tc.TABLE_NAME AND tc.TABLE_TYPE = 'TABLE'
            WHERE t.OWNER = UPPER(?)
            UNION ALL
            SELECT v.OWNER as SCHEMA_NAME, v.VIEW_NAME as OBJECT_NAME, 'VIEW' as OBJECT_TYPE,
                   NULL as TABLESPACE_NAME, NULL as NUM_ROWS, NULL as LAST_ANALYZED, vc.COMMENTS
            FROM ALL_VIEWS v
            LEFT JOIN ALL_TAB_COMMENTS vc ON v.OWNER = vc.OWNER AND v.VIEW_NAME = vc.TABLE_NAME AND vc.TABLE_TYPE = 'VIEW'
            WHERE v.OWNER = UPPER(?)
            ORDER BY SCHEMA_NAME, OBJECT_TYPE, OBJECT_NAME
            """ : """
            SELECT t.OWNER as SCHEMA_NAME, t.TABLE_NAME as OBJECT_NAME, 'TABLE' as OBJECT_TYPE,
                   t.TABLESPACE_NAME, t.NUM_ROWS, t.LAST_ANALYZED, tc.COMMENTS
            FROM ALL_TABLES t
            LEFT JOIN ALL_TAB_COMMENTS tc ON t.OWNER = tc.OWNER AND t.TABLE_NAME = tc.TABLE_NAME AND tc.TABLE_TYPE = 'TABLE'
            UNION ALL
            SELECT v.OWNER as SCHEMA_NAME, v.VIEW_NAME as OBJECT_NAME, 'VIEW' as OBJECT_TYPE,
                   NULL as TABLESPACE_NAME, NULL as NUM_ROWS, NULL as LAST_ANALYZED, vc.COMMENTS
            FROM ALL_VIEWS v
            LEFT JOIN ALL_TAB_COMMENTS vc ON v.OWNER = vc.OWNER AND v.VIEW_NAME = vc.TABLE_NAME AND vc.TABLE_TYPE = 'VIEW'
            ORDER BY SCHEMA_NAME, OBJECT_TYPE, OBJECT_NAME
            """;
        
        try (Connection conn = dataSource.getConnection();
             PreparedStatement stmt = conn.prepareStatement(query)) {
            if (schemaName != null) {
                stmt.setString(1, schemaName);
                stmt.setString(2, schemaName);
            }
            try (ResultSet rs = stmt.executeQuery()) {
                return resultSetToList(rs);
            }
        }
    }

    public List<Map<String, Object>> getTableColumns(String schemaName, String tableName) throws SQLException {
        String query = """
            SELECT c.COLUMN_NAME, c.DATA_TYPE, c.DATA_LENGTH, c.DATA_PRECISION, c.DATA_SCALE,
                   c.NULLABLE, c.DATA_DEFAULT, c.COLUMN_ID, cc.COMMENTS
            FROM ALL_TAB_COLUMNS c
            LEFT JOIN ALL_COL_COMMENTS cc ON c.OWNER = cc.OWNER AND c.TABLE_NAME = cc.TABLE_NAME AND c.COLUMN_NAME = cc.COLUMN_NAME
            WHERE c.OWNER = UPPER(?) AND c.TABLE_NAME = ?
            ORDER BY c.COLUMN_ID
            """;
        
        try (Connection conn = dataSource.getConnection();
            PreparedStatement stmt = conn.prepareStatement(query)) {
            stmt.setString(1, schemaName);
            stmt.setString(2, tableName);
            try (ResultSet rs = stmt.executeQuery()) {
                return resultSetToList(rs);
            }
        }
    }

    public List<Map<String, Object>> getTableConstraints(String schemaName, String tableName) throws SQLException {
        String query = """
            SELECT CONSTRAINT_NAME, CONSTRAINT_TYPE, SEARCH_CONDITION, STATUS, VALIDATED
            FROM ALL_CONSTRAINTS
            WHERE OWNER = UPPER(?) AND TABLE_NAME = ?
            ORDER BY CONSTRAINT_NAME
            """;
        
        try (Connection conn = dataSource.getConnection();
             PreparedStatement stmt = conn.prepareStatement(query)) {
            stmt.setString(1, schemaName);
            stmt.setString(2, tableName);
            try (ResultSet rs = stmt.executeQuery()) {
                return resultSetToList(rs);
            }
        }
    }

    public List<Map<String, Object>> getTableIndexes(String schemaName, String tableName) throws SQLException {
        String query = """
            SELECT INDEX_NAME, INDEX_TYPE, UNIQUENESS, STATUS, TABLESPACE_NAME
            FROM ALL_INDEXES
            WHERE OWNER = UPPER(?) AND TABLE_NAME = ?
            ORDER BY INDEX_NAME
            """;
        
        try (Connection conn = dataSource.getConnection();
             PreparedStatement stmt = conn.prepareStatement(query)) {
            stmt.setString(1, schemaName);
            stmt.setString(2, tableName);
            try (ResultSet rs = stmt.executeQuery()) {
                return resultSetToList(rs);
            }
        }
    }

    private List<Map<String, Object>> resultSetToList(ResultSet rs) throws SQLException {
        List<Map<String, Object>> results = new ArrayList<>();
        ResultSetMetaData metaData = rs.getMetaData();
        int columnCount = metaData.getColumnCount();
        
        while (rs.next()) {
            Map<String, Object> row = new LinkedHashMap<>();
            for (int i = 1; i <= columnCount; i++) {
                String columnName = metaData.getColumnName(i);
                Object value = rs.getObject(i);
                row.put(columnName, value);
            }
            results.add(row);
        }
        return results;
    }
}

