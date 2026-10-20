package tibero.mcp.db;

import java.math.BigDecimal;
import java.math.BigInteger;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Time;
import java.sql.Timestamp;
import java.sql.Types;
import java.time.LocalDateTime;
import java.util.Base64;
import java.util.Set;

/**
 * Converts JDBC column values into the JSON form shared with the Python server
 * (python/src/db/query_executor.py {@code _read_value}); see spec/README.md.
 */
public final class JsonValues {

    private static final Set<Integer> NUMERIC_TYPES = Set.of(Types.NUMERIC, Types.DECIMAL, Types.TINYINT,
            Types.SMALLINT, Types.INTEGER, Types.BIGINT);

    private static final Set<Integer> FLOAT_TYPES = Set.of(Types.FLOAT, Types.REAL, Types.DOUBLE);

    private static final Set<Integer> BOOLEAN_TYPES = Set.of(Types.BIT, Types.BOOLEAN);

    private static final Set<Integer> TIMESTAMP_TYPES = Set.of(Types.DATE, Types.TIMESTAMP,
            Types.TIMESTAMP_WITH_TIMEZONE);

    private static final Set<Integer> TIME_TYPES = Set.of(Types.TIME, Types.TIME_WITH_TIMEZONE);

    private static final Set<Integer> BINARY_TYPES = Set.of(Types.BINARY, Types.VARBINARY, Types.LONGVARBINARY,
            Types.BLOB);

    private static final BigInteger MAX_SAFE_INTEGER = BigInteger.valueOf((1L << 53) - 1);

    private final int maxCellChars;

    public JsonValues(int maxCellChars) {
        this.maxCellChars = maxCellChars;
    }

    public Object read(ResultSet rs, int column, int sqlType) throws SQLException {
        if (BOOLEAN_TYPES.contains(sqlType)) {
            boolean value = rs.getBoolean(column);
            return rs.wasNull() ? null : value;
        }
        if (NUMERIC_TYPES.contains(sqlType)) {
            BigDecimal value = rs.getBigDecimal(column);
            return value == null ? null : decimalToJson(value);
        }
        if (FLOAT_TYPES.contains(sqlType)) {
            double value = rs.getDouble(column);
            return rs.wasNull() ? null : value;
        }
        if (TIMESTAMP_TYPES.contains(sqlType)) {
            Timestamp value = rs.getTimestamp(column);
            return value == null ? null : formatTimestamp(value.toLocalDateTime());
        }
        if (TIME_TYPES.contains(sqlType)) {
            Time value = rs.getTime(column);
            return value == null ? null : value.toString();
        }
        if (BINARY_TYPES.contains(sqlType)) {
            byte[] value = rs.getBytes(column);
            return value == null ? null : truncate("base64:" + Base64.getEncoder().encodeToString(value));
        }
        String value = rs.getString(column);
        return value == null ? null : truncate(value);
    }

    /** Integral values become integers while exactly representable, larger ones strings; fractions doubles. */
    public static Object decimalToJson(BigDecimal value) {
        BigDecimal stripped = value.stripTrailingZeros();
        if (stripped.scale() <= 0) {
            BigInteger integral = stripped.toBigIntegerExact();
            return integral.abs().compareTo(MAX_SAFE_INTEGER) <= 0 ? (Object) integral.longValue() : integral.toString();
        }
        return value.doubleValue();
    }

    /** Matches Python's str(datetime): microseconds only when non-zero. */
    static String formatTimestamp(LocalDateTime local) {
        String text = String.format("%04d-%02d-%02d %02d:%02d:%02d", local.getYear(), local.getMonthValue(),
                local.getDayOfMonth(), local.getHour(), local.getMinute(), local.getSecond());
        int micros = local.getNano() / 1000;
        return micros == 0 ? text : text + String.format(".%06d", micros);
    }

    /** Cap a text cell at maxCellChars code points (Python counts code points, not UTF-16 units). */
    public String truncate(String text) {
        int length = text.codePointCount(0, text.length());
        if (length <= maxCellChars) {
            return text;
        }
        int end = text.offsetByCodePoints(0, maxCellChars);
        return text.substring(0, end) + "...[truncated " + (length - maxCellChars) + " chars]";
    }
}
