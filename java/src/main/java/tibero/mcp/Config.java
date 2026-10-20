package tibero.mcp;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Settings shared with the Python server: the same environment variables, and the
 * same optional {@code mcp.cfg} file (KEY=VALUE lines) in the working directory.
 * Environment variables win over the file, as with python-dotenv.
 */
public final class Config {

    private final Map<String, String> values;

    private Config(Map<String, String> values) {
        this.values = values;
    }

    public static Config load() {
        Map<String, String> merged = new HashMap<>();
        Path file = Path.of(System.getenv().getOrDefault("MCP_CONFIG_FILE", "mcp.cfg"));
        if (Files.isRegularFile(file)) {
            try {
                merged.putAll(parse(Files.readAllLines(file, StandardCharsets.UTF_8)));
            }
            catch (IOException e) {
                throw new IllegalStateException("Cannot read " + file + ": " + e.getMessage(), e);
            }
        }
        merged.putAll(System.getenv());
        return new Config(merged);
    }

    public static Config of(Map<String, String> values) {
        return new Config(new HashMap<>(values));
    }

    static Map<String, String> parse(List<String> lines) {
        Map<String, String> result = new HashMap<>();
        for (String raw : lines) {
            String line = raw.strip();
            if (line.isEmpty() || line.startsWith("#") || !line.contains("=")) {
                continue;
            }
            if (line.startsWith("export ")) {
                line = line.substring(7).strip();
            }
            int eq = line.indexOf('=');
            String key = line.substring(0, eq).strip();
            String value = line.substring(eq + 1).strip();
            if (value.length() >= 2 && (value.startsWith("\"") && value.endsWith("\"") || value.startsWith("'") && value.endsWith("'"))) {
                value = value.substring(1, value.length() - 1);
            }
            else {
                int comment = value.indexOf(" #");
                if (comment >= 0) {
                    value = value.substring(0, comment).strip();
                }
            }
            result.put(key, value);
        }
        return result;
    }

    public String get(String name, String defaultValue) {
        String value = values.get(name);
        return value == null || value.isEmpty() ? defaultValue : value;
    }

    public String get(String name) {
        return get(name, null);
    }

    public int getInt(String name, int defaultValue) {
        String value = get(name);
        return value == null ? defaultValue : Integer.parseInt(value.strip());
    }

    /** Same truthy set as the Python server: 1, true, yes, on (case-insensitive). */
    public boolean flag(String name) {
        return isTruthy(values.get(name));
    }

    public static boolean isTruthy(String value) {
        if (value == null) {
            return false;
        }
        return List.of("1", "true", "yes", "on").contains(value.strip().toLowerCase(Locale.ROOT));
    }

    public List<String> list(String name) {
        List<String> result = new ArrayList<>();
        String value = get(name);
        if (value != null) {
            for (String part : value.split(",")) {
                if (!part.strip().isEmpty()) {
                    result.add(part.strip());
                }
            }
        }
        return result;
    }
}
