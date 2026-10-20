package tibero.mcp.tools;

import java.math.BigDecimal;

/**
 * Python {@code str()} formatting for values embedded in text the Python server
 * builds with f-strings (plan_text), so both servers produce the same characters.
 */
final class PyText {

    private PyText() {
    }

    /** Python {@code str(value)}: None, float repr (shortest digits, e-notation outside 1e-4..1e16), else toString. */
    static String str(Object value) {
        if (value == null) {
            return "None";
        }
        if (value instanceof Double d) {
            return floatRepr(d);
        }
        if (value instanceof Float f) {
            return floatRepr(f.doubleValue());
        }
        if (value instanceof Boolean b) {
            return b ? "True" : "False";
        }
        return value.toString();
    }

    static String repr(Object value) {
        return str(value);
    }

    static String floatRepr(double d) {
        if (Double.isNaN(d)) {
            return "nan";
        }
        if (Double.isInfinite(d)) {
            return d > 0 ? "inf" : "-inf";
        }
        if (d == 0) {
            return (1 / d < 0) ? "-0.0" : "0.0";
        }
        String sign = d < 0 ? "-" : "";
        // Double.toString yields the shortest round-tripping digits (JDK 19+), as Python's repr does.
        BigDecimal value = new BigDecimal(Double.toString(Math.abs(d))).stripTrailingZeros();
        String digits = value.unscaledValue().toString();
        int exponent = digits.length() - 1 - value.scale();
        if (exponent < -4 || exponent >= 16) {
            String mantissa = digits.length() == 1 ? digits : digits.charAt(0) + "." + digits.substring(1);
            return sign + mantissa + "e" + (exponent < 0 ? "-" : "+") + String.format("%02d", Math.abs(exponent));
        }
        String plain = value.toPlainString();
        return sign + (plain.contains(".") ? plain : plain + ".0");
    }

    /** First {@code limit} code points, for log lines (Python {@code text[:limit]}). */
    static String head(String text, int limit) {
        if (text == null) {
            return "None";
        }
        int count = text.codePointCount(0, text.length());
        return count <= limit ? text : text.substring(0, text.offsetByCodePoints(0, limit));
    }
}
