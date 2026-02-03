package tibero.mcp;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.WebApplicationType;

@SpringBootApplication
public class TiberoMcpServerApplication {

    public static void main(String[] args) {
        boolean httpMode = Boolean.getBoolean("mcp.mode.http");  // JVM 옵션으로 선택 가능

        SpringApplication app = new SpringApplication(TiberoMcpServerApplication.class);
        if (!httpMode) {
            app.setLogStartupInfo(false);
        }

        if (httpMode) {
            // HTTP WebMVC MCP 서버 모드
            app.setWebApplicationType(WebApplicationType.SERVLET);
        } else {
            // 기본 STDIO MCP 서버 모드
            app.setWebApplicationType(WebApplicationType.NONE);
        }

        app.run(args);
    }
}
