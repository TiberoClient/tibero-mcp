package tibero.mcp.tools;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.Test;

import io.modelcontextprotocol.json.McpJsonDefaults;

class SpecTest {

    @Test
    @SuppressWarnings("unchecked")
    void readOnlyKeepsExactlyReadOnlyTools() {
        TiberoTools tools = new TiberoTools(null, McpJsonDefaults.getMapper());
        Map<String, Object> spec = TiberoTools.loadSpec(McpJsonDefaults.getMapper());
        List<String> all = ((List<Map<String, Object>>) spec.get("tools")).stream()
            .map(t -> (String) t.get("name"))
            .toList();
        List<String> readOnly = ((List<Map<String, Object>>) spec.get("tools")).stream()
            .filter(t -> Boolean.TRUE.equals(((Map<String, Object>) t.get("annotations")).get("readOnlyHint")))
            .map(t -> (String) t.get("name"))
            .toList();
        assertEquals(all, tools.entries(false).stream().map(e -> e.tool().name()).toList());
        assertEquals(readOnly, tools.entries(true).stream().map(e -> e.tool().name()).toList());
        assertEquals(List.of("execute_query", "get_schema", "get_table_info", "explain_plan", "sample_table"), readOnly);
    }
}
