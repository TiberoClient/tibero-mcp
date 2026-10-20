package tibero.mcp.db;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.Test;

import tibero.mcp.Cases;
import tibero.mcp.Config;
import tibero.mcp.ToolException;

class SqlRulesTest {

    @Test
    void leadingKeyword() {
        for (List<Object> c : Cases.pairs("leading_keyword")) {
            assertEquals(c.get(1), SqlRules.leadingKeyword((String) c.get(0)), String.valueOf(c.get(0)));
        }
    }

    @Test
    void normalize() {
        for (List<Object> c : Cases.pairs("normalize")) {
            assertEquals(c.get(1), SqlRules.normalizeStatement((String) c.get(0)));
        }
        for (Object sql : Cases.list("normalize_rejects")) {
            assertThrows(ToolException.class, () -> SqlRules.normalizeStatement((String) sql));
        }
    }

    @Test
    void selectGuard() {
        for (Object sql : Cases.list("select_rejects")) {
            assertThrows(ToolException.class, () -> SqlRules.ensureSelect((String) sql), (String) sql);
        }
        for (Object sql : Cases.list("select_accepts")) {
            assertDoesNotThrow(() -> SqlRules.ensureSelect((String) sql), (String) sql);
        }
    }

    @Test
    void dmlGuard() {
        for (Object sql : Cases.list("dml_rejects")) {
            assertThrows(ToolException.class, () -> SqlRules.ensureDml((String) sql), (String) sql);
        }
        for (Object sql : Cases.list("dml_accepts")) {
            assertDoesNotThrow(() -> SqlRules.ensureDml((String) sql), (String) sql);
        }
    }

    @Test
    void quoteIdentifier() {
        for (List<Object> c : Cases.pairs("quote_identifier")) {
            assertEquals(c.get(1), SqlRules.quoteIdentifier((String) c.get(0)));
        }
    }

    @Test
    @SuppressWarnings("unchecked")
    void uniqueLabels() {
        for (List<Object> c : Cases.pairs("unique_labels")) {
            assertEquals(c.get(1), SqlRules.uniqueLabels((List<String>) c.get(0)));
        }
    }

    @Test
    void decimalToJson() {
        for (List<Object> c : Cases.pairs("decimal")) {
            Object actual = JsonValues.decimalToJson(new BigDecimal((String) c.get(0)));
            Object expected = c.get(1);
            if (expected instanceof Number n && !(expected instanceof Double)) {
                assertEquals(n.longValue(), actual, String.valueOf(c.get(0)));
            }
            else {
                assertEquals(expected, actual, String.valueOf(c.get(0)));
            }
        }
    }

    @Test
    @SuppressWarnings("unchecked")
    void truncate() {
        Map<String, Object> spec = (Map<String, Object>) Cases.all().get("truncate");
        JsonValues values = new JsonValues(((Number) spec.get("max_chars")).intValue());
        for (List<Object> c : (List<List<Object>>) spec.get("cases")) {
            assertEquals(Cases.expand(c.get(1)), values.truncate(Cases.expand(c.get(0))));
        }
    }

    @Test
    void envFlag() {
        for (List<Object> c : Cases.pairs("env_flag")) {
            assertEquals(c.get(1), Config.isTruthy((String) c.get(0)), String.valueOf(c.get(0)));
        }
    }
}
