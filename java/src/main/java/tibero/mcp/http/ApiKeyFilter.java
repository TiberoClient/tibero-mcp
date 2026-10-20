package tibero.mcp.http;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.List;
import java.util.Locale;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import jakarta.servlet.Filter;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.ServletRequest;
import jakarta.servlet.ServletResponse;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

/**
 * API-key authentication and a key-redacting access log, mirroring
 * python/src/mcp/auth.py. The key is accepted as {@code Authorization: Bearer},
 * {@code X-API-Key}, or a leading path segment ({@code /<key>/mcp}).
 */
public class ApiKeyFilter implements Filter {

    private static final Logger access = LoggerFactory.getLogger("tibero.mcp.access");

    static final String UNAUTHORIZED_BODY = "{\"error\": \"unauthorized\", \"error_description\": \"Missing or invalid API key\"}";

    public static final String HEALTH_PATH = "/healthz";

    private final List<String> keys;

    private final String mcpPath;

    public ApiKeyFilter(List<String> keys, String mcpPath) {
        this.keys = List.copyOf(keys);
        this.mcpPath = mcpPath;
    }

    /** Compare against every key so timing does not reveal which one matched. */
    static boolean matches(String candidate, List<String> keys) {
        boolean found = false;
        byte[] given = candidate.getBytes(StandardCharsets.UTF_8);
        for (String key : keys) {
            found |= MessageDigest.isEqual(given, key.getBytes(StandardCharsets.UTF_8));
        }
        return found;
    }

    /** Splits {@code /<key>/rest} into the rest when the first segment is a valid key, else null. */
    static String stripPathKey(String path, List<String> keys) {
        String trimmed = path.replaceFirst("^/+", "");
        int slash = trimmed.indexOf('/');
        if (slash < 0 || keys.isEmpty()) {
            return null;
        }
        return matches(trimmed.substring(0, slash), keys) ? "/" + trimmed.substring(slash + 1) : null;
    }

    static boolean headerKeyOk(HttpServletRequest request, List<String> keys) {
        String authorization = request.getHeader("Authorization");
        if (authorization != null && authorization.length() >= 7
                && authorization.substring(0, 7).toLowerCase(Locale.ROOT).equals("bearer ")
                && matches(authorization.substring(7).strip(), keys)) {
            return true;
        }
        String apiKey = request.getHeader("X-API-Key");
        return apiKey != null && !apiKey.isEmpty() && matches(apiKey.strip(), keys);
    }

    @Override
    public void doFilter(ServletRequest req, ServletResponse res, FilterChain chain)
            throws IOException, ServletException {
        HttpServletRequest request = (HttpServletRequest) req;
        HttpServletResponse response = (HttpServletResponse) res;
        long started = System.nanoTime();
        String rawPath = request.getRequestURI();
        String stripped = stripPathKey(rawPath, keys);
        String path = stripped != null ? stripped : rawPath;
        try {
            boolean authorized = keys.isEmpty() || path.equals(HEALTH_PATH) || stripped != null
                    || headerKeyOk(request, keys);
            if (!authorized) {
                byte[] body = UNAUTHORIZED_BODY.getBytes(StandardCharsets.UTF_8);
                response.setStatus(401);
                response.setContentType("application/json");
                response.setContentLength(body.length);
                response.getOutputStream().write(body);
                return;
            }
            if (path.equals(HEALTH_PATH)) {
                if (!"GET".equals(request.getMethod())) {
                    response.sendError(405);
                    return;
                }
                byte[] body = "{\"status\":\"ok\"}".getBytes(StandardCharsets.UTF_8);
                response.setStatus(200);
                response.setContentType("application/json");
                response.setContentLength(body.length);
                response.getOutputStream().write(body);
                return;
            }
            if (!path.equals(mcpPath)) {
                response.setStatus(404);
                response.setContentType("text/plain; charset=utf-8");
                response.getWriter().write("Not Found");
                return;
            }
            chain.doFilter(request, response);
        }
        finally {
            String client = request.getHeader("X-Real-IP") != null ? request.getHeader("X-Real-IP")
                    : request.getRemoteAddr();
            String logged = stripped != null ? "/<key>" + (path.startsWith("/") ? path : "/" + path) : rawPath;
            access.info("{} \"{} {}\" {} {}ms", client, request.getMethod(), logged, response.getStatus(),
                    (System.nanoTime() - started) / 1_000_000);
        }
    }
}
