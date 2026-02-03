"""Tibero database connection module using JDBC."""

from __future__ import annotations

import os
import jaydebeapi
from pathlib import Path
from loguru import logger


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
        """Find JDBC driver JAR file."""
        # python/ 디렉토리 기준으로 lib/ 찾기
        project_root = Path(__file__).parent.parent.parent
        lib_dir = project_root / "lib"
        
        # Look for tbjdbc8 JAR files
        jar_files = list(lib_dir.glob("tbjdbc8*.jar"))
        if jar_files:
            return str(jar_files[0])

        raise FileNotFoundError(
            f"Tibero JDBC driver not found. Please download it to {lib_dir}"
        )

    def connect(self):
        """Establish database connection."""
        if self.connection:
            return self.connection

        driver_class = "com.tmax.tibero.jdbc.TbDriver"
        jdbc_url = f"jdbc:tibero:thin:@{self.host}:{self.port}:{self.database}"

        logger.info(f"Connecting to Tibero: {self.host}:{self.port}/{self.database}")
        logger.debug(f"Using JDBC driver: {self.jdbc_jar_path}")

        try:
            self.connection = jaydebeapi.connect(
                driver_class,
                jdbc_url,
                [self.user, self.password],
                self.jdbc_jar_path,
            )
            logger.info("Successfully connected to Tibero database")
            return self.connection
        except Exception as e:
            logger.error(f"Failed to connect to Tibero: {e}")
            raise

    def close(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.info("Database connection closed")

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

