"""Simple user quota limiter where each user have fixed quota."""

import logging
from datetime import datetime

from ols.app.models.config import PostgresConfig
from ols.src.quota.quota_exceed_error import QuotaExceedError
from ols.src.quota.quota_limiter import QuotaLimiter

logger = logging.getLogger(__name__)


class UserQuotaLimiter(QuotaLimiter):
    """Simple user quota limiter where each user have fixed quota."""

    CREATE_QUOTA_TABLE = """
        CREATE TABLE IF NOT EXISTS quota_limits (
            id              text NOT NULL,
            subject         char(1) NOT NULL,
            quota_limit     int NOT NULL,
            available       int,
            updated_at      timestamp with time zone,
            revoked_at      timestamp with time zone,
            PRIMARY KEY(id, subject)
        );
        """

    INIT_QUOTA = """
        INSERT INTO quota_limits (id, subject, quota_limit, available, revoked_at)
        VALUES (%s, %s, %s, %s, %s)
        """

    SELECT_QUOTA = """
        SELECT available
          FROM quota_limits
         WHERE id=%s and subject=%s LIMIT 1
        """

    SET_AVAILABLE_QUOTA = """
        UPDATE quota_limits
           SET available=%s, updated_at=%s
         WHERE id=%s and subject=%s
        """

    UPDATE_AVAILABLE_QUOTA = """
        UPDATE quota_limits
           SET available=available+%s, updated_at=%s
         WHERE id=%s and subject=%s
        """

    def __init__(
        self,
        config: PostgresConfig,
        initial_quota: int = 0,
        increase_by: int = 0,
    ) -> None:
        """Initialize quota limiter storage."""
        self.subject = "u"  # user
        self.initial_quota = initial_quota
        self.increase_by = increase_by

        # initialize connection to DB
        self.connect(config)

        try:
            self._initialize_tables()
        except Exception as e:
            self.connection.close()
            logger.exception("Error initializing Postgres database:\n%s", e)
            raise

    def available_quota(self, user_id: str = "") -> int:
        """Retrieve available quota for given user."""
        with self.connection.cursor() as cursor:
            cursor.execute(
                UserQuotaLimiter.SELECT_QUOTA,
                (user_id, self.subject),
            )
            value = cursor.fetchone()
            if value is None:
                self._init_quota(user_id)
                return self.initial_quota
            return value[0]

    def revoke_quota(self, user_id: str = "") -> None:
        """Revoke quota for given user."""
        # timestamp to be used
        updated_at = datetime.now()

        with self.connection.cursor() as cursor:
            cursor.execute(
                UserQuotaLimiter.SET_AVAILABLE_QUOTA,
                (self.initial_quota, updated_at, user_id, self.subject),
            )
            self.connection.commit()

    def increase_quota(self, user_id: str = "") -> None:
        """Increase quota for given user."""
        # timestamp to be used
        updated_at = datetime.now()

        with self.connection.cursor() as cursor:
            cursor.execute(
                UserQuotaLimiter.UPDATE_AVAILABLE_QUOTA,
                (self.increase_by, updated_at, user_id, self.subject),
            )
            self.connection.commit()

    def consume_tokens(
        self, input_tokens: int = 0, output_tokens: int = 0, user_id: str = ""
    ) -> None:
        """Consume tokens by given user."""
        to_be_consumed = input_tokens + output_tokens

        # note that checking available tokens and decreasing quota operations
        # are performed in a transaction
        with self.connection.cursor() as cursor:
            cursor.execute(
                UserQuotaLimiter.SELECT_QUOTA,
                (user_id, self.subject),
            )
            value = cursor.fetchone()
            if value is None:
                available = 0
            else:
                available = value[0]

            # check if user still have available tokens to be consumed
            if available < to_be_consumed:
                e = QuotaExceedError(user_id, available, to_be_consumed)
                logger.exception("Quota exceed: %s", e)
                raise e

            # timestamp to be used
            updated_at = datetime.now()

            cursor.execute(
                UserQuotaLimiter.UPDATE_AVAILABLE_QUOTA,
                (-to_be_consumed, updated_at, user_id, self.subject),
            )
            self.connection.commit()

    def _initialize_tables(self) -> None:
        """Initialize tables used by quota limiter."""
        cursor = self.connection.cursor()
        cursor.execute(UserQuotaLimiter.CREATE_QUOTA_TABLE)
        cursor.close()
        self.connection.commit()

    def _init_quota(self, user_id: str) -> None:
        """Initialize quota for given user."""
        # timestamp to be used
        revoked_at = datetime.now()

        with self.connection.cursor() as cursor:
            cursor.execute(
                UserQuotaLimiter.INIT_QUOTA,
                (
                    user_id,
                    self.subject,
                    self.initial_quota,
                    self.initial_quota,
                    revoked_at,
                ),
            )
            self.connection.commit()
