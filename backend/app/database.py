import os

import mysql.connector
from mysql.connector import pooling
from dotenv import load_dotenv


load_dotenv()


DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "ai_reviewer"),
}


DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))


connection_pool = mysql.connector.pooling.MySQLConnectionPool(
    pool_name="ai_reviewer_pool",
    pool_size=DB_POOL_SIZE,
    pool_reset_session=True,
    **DB_CONFIG,
)


def get_db():
    """
    Return a healthy MySQL connection configured to UTC.

    Every pooled connection is explicitly configured at checkout.
    This prevents application behaviour from depending on the
    database/server/session timezone configuration.
    """

    connection = connection_pool.get_connection()

    if not connection.is_connected():
        connection.reconnect(
            attempts=3,
            delay=1,
        )

    cursor = connection.cursor()

    try:
        # -------------------------------------------------
        # IMPORTANT:
        # Every MySQL session used by the application
        # operates in UTC.
        # -------------------------------------------------

        cursor.execute("SET time_zone = '+00:00'")

    finally:
        cursor.close()

    return connection