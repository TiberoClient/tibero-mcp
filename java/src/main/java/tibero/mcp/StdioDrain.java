package tibero.mcp;

import java.io.ByteArrayOutputStream;
import java.io.FilterInputStream;
import java.io.FilterOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

import io.modelcontextprotocol.json.McpJsonMapper;
import io.modelcontextprotocol.json.TypeRef;

/**
 * Lets the stdio server finish answering before it sees end of input.
 *
 * On EOF the SDK's stdio transport closes the session at once, dropping replies to
 * requests still being handled (a client that writes a request and closes stdin gets
 * nothing). This pair of streams counts JSON-RPC requests read and responses written,
 * and holds back EOF until every request has been answered (or the wait times out),
 * matching the Python server, which answers and then exits.
 */
final class StdioDrain {

    private final McpJsonMapper json;

    private final long maxWaitMillis;

    private final Object lock = new Object();

    private int pending;

    final CountDownLatch finished = new CountDownLatch(1);

    StdioDrain(McpJsonMapper json, long maxWaitMillis) {
        this.json = json;
        this.maxWaitMillis = maxWaitMillis;
    }

    private Map<String, Object> parse(byte[] line) {
        try {
            return json.readValue(line, new TypeRef<Map<String, Object>>() {
            });
        }
        catch (Exception e) {
            return Map.of();
        }
    }

    private void onInputLine(byte[] line) {
        Map<String, Object> message = parse(line);
        if (message.containsKey("method") && message.get("id") != null) {
            synchronized (lock) {
                pending++;
            }
        }
    }

    private void onOutputLine(byte[] line) {
        Map<String, Object> message = parse(line);
        if (!message.containsKey("method") && message.get("id") != null) {
            synchronized (lock) {
                pending--;
                lock.notifyAll();
            }
        }
    }

    private void awaitAnswered() {
        long deadline = System.currentTimeMillis() + maxWaitMillis;
        synchronized (lock) {
            while (pending > 0) {
                long left = deadline - System.currentTimeMillis();
                if (left <= 0) {
                    return;
                }
                try {
                    lock.wait(left);
                }
                catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    return;
                }
            }
        }
    }

    InputStream input(InputStream in) {
        return new FilterInputStream(in) {
            private final ByteArrayOutputStream line = new ByteArrayOutputStream();

            private int track(int value) {
                if (value == '\n') {
                    onInputLine(line.toByteArray());
                    line.reset();
                }
                else if (value >= 0) {
                    line.write(value);
                }
                return value;
            }

            private void atEof() {
                if (line.size() > 0) {
                    onInputLine(line.toByteArray());
                    line.reset();
                }
                awaitAnswered();
                finished.countDown();
            }

            @Override
            public int read() throws IOException {
                int value = super.read();
                if (value < 0) {
                    atEof();
                }
                return track(value);
            }

            @Override
            public int read(byte[] buffer, int offset, int length) throws IOException {
                int count = super.read(buffer, offset, length);
                if (count < 0) {
                    atEof();
                    return count;
                }
                for (int i = offset; i < offset + count; i++) {
                    track(buffer[i] & 0xff);
                }
                return count;
            }
        };
    }

    OutputStream output(OutputStream out) {
        return new FilterOutputStream(out) {
            private final ByteArrayOutputStream line = new ByteArrayOutputStream();

            @Override
            public void write(int b) throws IOException {
                out.write(b);
                if (b == '\n') {
                    out.flush();
                    onOutputLine(line.toByteArray());
                    line.reset();
                }
                else {
                    line.write(b);
                }
            }

            @Override
            public void write(byte[] buffer, int offset, int length) throws IOException {
                out.write(buffer, offset, length);
                for (int i = offset; i < offset + length; i++) {
                    if (buffer[i] == '\n') {
                        out.flush();
                        onOutputLine(line.toByteArray());
                        line.reset();
                    }
                    else {
                        line.write(buffer[i]);
                    }
                }
            }
        };
    }

    boolean awaitFinished() throws InterruptedException {
        finished.await();
        return true;
    }

    static long seconds(int value) {
        return TimeUnit.SECONDS.toMillis(value);
    }
}
