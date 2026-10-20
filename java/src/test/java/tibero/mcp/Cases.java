package tibero.mcp;

import java.io.IOException;
import java.io.InputStream;
import java.util.List;
import java.util.Map;

import io.modelcontextprotocol.json.McpJsonDefaults;
import io.modelcontextprotocol.json.TypeRef;

/** The vectors in spec/conformance/cases.json, shared with the Python tests. */
public final class Cases {

    private static Map<String, Object> cases;

    private Cases() {
    }

    public static synchronized Map<String, Object> all() {
        if (cases == null) {
            try (InputStream in = Cases.class.getResourceAsStream("/conformance/cases.json")) {
                cases = McpJsonDefaults.getMapper().readValue(in.readAllBytes(), new TypeRef<Map<String, Object>>() {
                });
            }
            catch (IOException e) {
                throw new IllegalStateException(e);
            }
        }
        return cases;
    }

    @SuppressWarnings("unchecked")
    public static List<Object> list(String name) {
        return (List<Object>) all().get(name);
    }

    @SuppressWarnings("unchecked")
    public static List<List<Object>> pairs(String name) {
        return (List<List<Object>>) all().get(name);
    }

    @SuppressWarnings("unchecked")
    public static String expand(Object spec) {
        Map<String, Object> map = (Map<String, Object>) spec;
        return ((String) map.get("repeat")).repeat(((Number) map.get("count")).intValue())
                + map.getOrDefault("suffix", "");
    }
}
