"""Tibero database connection module using JDBC."""

from __future__ import annotations

import os
import threading
import jaydebeapi
from pathlib import Path
from loguru import logger


_CONNECT_LOCK = threading.Lock()


class TiberoConnection:
    """Tibero database connection manager."""

    def __init__(
        self,
        host: str,
        port: int,
        database: str,
        user: str,
        password: str,
        jdbc_jar_path: str | None = None,
    ):
        """
        Initialize Tibero connection parameters.

        Args:
            host: Database host
            port: Database port
            database: Database name
            user: Username
            password: Password
            jdbc_jar_path: Path to JDBC driver JAR file
        """
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.jdbc_jar_path = jdbc_jar_path or self._find_jdbc_jar()
        self.connection = None

    def _find_jdbc_jar(self) -> str:
        """Find the JDBC driver: TIBERO_JDBC_JAR, else the single tbjdbc*.jar in lib/.

        The Java server uses com.tmaxtibero:tbjdbc17 at the same version (see
        java/build.gradle and the Dockerfile), so both read values through one driver.
        """
        explicit = os.getenv("TIBERO_JDBC_JAR")
        if explicit:
            return explicit
        lib_dir = Path(__file__).parent.parent.parent / "lib"
        jar_files = sorted(lib_dir.glob("tbjdbc*.jar"))
        if len(jar_files) == 1:
            return str(jar_files[0])
        if jar_files:
            raise FileNotFoundError(f"Several Tibero JDBC drivers in {lib_dir}: {[p.name for p in jar_files]}; keep one")
        raise FileNotFoundError(
            f"Tibero JDBC driver not found. Download com.tmaxtibero:tbjdbc17 to {lib_dir} or set TIBERO_JDBC_JAR"
        )

    def connect(self):
        """Establish database connection."""
        if self.connection:
            return self.connection

        driver_class = "com.tmax.tibero.jdbc.TbDriver"
        jdbc_url = f"jdbc:tibero:thin:@{self.host}:{self.port}:{self.database}"

        logger.debug(f"Connecting to Tibero: {self.host}:{self.port}/{self.database}")
        logger.debug(f"Using JDBC driver: {self.jdbc_jar_path}")

        try:
            # The first connect starts the JVM; two threads doing that at once fail.
            with _CONNECT_LOCK:
                self.connection = jaydebeapi.connect(
                    driver_class,
                    jdbc_url,
                    [self.user, self.password],
                    self.jdbc_jar_path,
                )
            logger.debug("Connected to Tibero database")
            return self.connection
        except Exception as e:
            logger.error(f"Failed to connect to Tibero: {e}")
            raise

    def close(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None

    def __enter__(self) -> jaydebeapi.Connection:
        """Context manager entry."""
        return self.connect()

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: type[BaseException] | None) -> None:
        """Context manager exit."""
        self.close()


def get_connection() -> jaydebeapi.Connection:
    """
    Get Tibero database connection using environment variables.

    Returns:
        Database connection object

    Raises:
        ValueError: If required environment variables are not set
        FileNotFoundError: If JDBC driver JAR is not found
    """
    host = os.getenv("TIBERO_HOST")
    port = int(os.getenv("TIBERO_PORT", "8629"))
    database = os.getenv("TIBERO_DATABASE")
    user = os.getenv("TIBERO_USER")
    password = os.getenv("TIBERO_PASSWORD")

    if not all([host, database, user, password]):
        raise ValueError(
            "Missing required environment variables: "
            "TIBERO_HOST, TIBERO_DATABASE, TIBERO_USER, TIBERO_PASSWORD"
        )

    connector = TiberoConnection(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
    )

    return connector.connect()

