package tibero.mcp.http;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;

import org.junit.jupiter.api.Test;

class ApiKeyFilterTest {

    private static final List<String> KEYS = List.of("first", "second");

    @Test
    void pathKeyIsStripped() {
        assertEquals("/mcp", ApiKeyFilter.stripPathKey("/second/mcp", KEYS));
        assertNull(ApiKeyFilter.stripPathKey("/wrong/mcp", KEYS));
        assertNull(ApiKeyFilter.stripPathKey("/mcp", KEYS));
        assertNull(ApiKeyFilter.stripPathKey("/first/mcp", List.of()));
    }

    @Test
    void matchesOnlyExactKeys() {
        assertTrue(ApiKeyFilter.matches("first", KEYS));
        assertFalse(ApiKeyFilter.matches("firs", KEYS));
        assertFalse(ApiKeyFilter.matches("", KEYS));
    }
}
