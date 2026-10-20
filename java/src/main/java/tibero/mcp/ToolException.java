package tibero.mcp;

/**
 * A failure the model should see and can act on (bad SQL, missing table, rejected
 * statement). Reported as an {@code isError} tool result, like the Python ToolError.
 */
public class ToolException extends RuntimeException {

    public ToolException(String message) {
        super(message);
    }

    public ToolException(String message, Throwable cause) {
        super(message, cause);
    }
}
