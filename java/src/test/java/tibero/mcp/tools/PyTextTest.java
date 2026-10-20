package tibero.mcp.tools;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

/** Expected strings are Python's str(float) output. */
class PyTextTest {

    @Test
    void floatReprMatchesPython() {
        assertEquals("12.0", PyText.floatRepr(12.0));
        assertEquals("0.1", PyText.floatRepr(0.1));
        assertEquals("1.5", PyText.floatRepr(1.5));
        assertEquals("123456789.0", PyText.floatRepr(123456789.0));
        assertEquals("1e+16", PyText.floatRepr(1e16));
        assertEquals("1.2345e+20", PyText.floatRepr(1.2345e20));
        assertEquals("0.0001", PyText.floatRepr(0.0001));
        assertEquals("1.5e-05", PyText.floatRepr(1.5e-5));
        assertEquals("-2.5", PyText.floatRepr(-2.5));
        assertEquals("0.0", PyText.floatRepr(0.0));
        assertEquals("None", PyText.str(null));
    }
}
