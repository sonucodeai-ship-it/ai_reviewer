from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.database import get_db
from app.main import now_utc, serialize_datetime


router = APIRouter(prefix="/api/coins", tags=["Coins"])


# ============================================================
# COIN TRANSACTION RULES
# ============================================================
#
# This file is the single source of truth for coin billing.
#
# IMPORTANT:
#   Feature endpoints must NOT calculate coin costs, inspect
#   memberships, or update wallet tables themselves.
#
#   They call authorize_usage(..., rule_no=<number>, phase=...).
#   This module then owns the complete billing decision:
#       rule -> entitlement -> wallet -> deduction -> ledger
#
# Example:
#   Review      -> rule_no=1
#   Website     -> rule_no=2
#   Membership  -> subscription rule (3, 4, ...)
#
# All billing validation, membership checks, wallet locking,
# deductions, subscription creation, transaction history, and
# billing errors are handled here.
# ============================================================

COIN_TRANSACTION_RULES = {
    # --------------------------------------------------------
    # Usage rules
    # --------------------------------------------------------
    1: {
        "rule_no": 1,
        "code": "review_generated",
        "name": "Review generated",
        "description": "Every successful review generation deducts 1 coin.",
        "coins": 1,
        "type": "usage",
    },
    2: {
        "rule_no": 2,
        "code": "website_published",
        "name": "Website published",
        "description": "Every successfully published website version deducts 20 coins.",
        "coins": 20,
        "type": "usage",
    },

    # --------------------------------------------------------
    # Subscription rules
    # --------------------------------------------------------
    # A subscription rule grants the usage entitlements listed in
    # `included_usage_rules`. Adding another subscription therefore
    # does not require another billing function.
    3: {
        "rule_no": 3,
        "code": "monthly_unlimited",
        "name": "Monthly unlimited membership",
        "description": "Unlimited website generation and review generation for one month.",
        "coins": 100,
        "type": "subscription",
        "duration_days": 30,
        "included_usage_rules": [1, 2],
    },
    4: {
        "rule_no": 4,
        "code": "yearly_unlimited",
        "name": "Yearly unlimited membership",
        "description": "Unlimited website generation and review generation for one year.",
        "coins": 999,
        "type": "subscription",
        "duration_days": 365,
        "included_usage_rules": [1, 2],
    },
}

REVIEW_RULE_NO = 1
WEBSITE_RULE_NO = 2
DEFAULT_SUBSCRIPTION_RULE_NO = 3
YEARLY_SUBSCRIPTION_RULE_NO = 4
# Backward-compatible name for existing imports.
SUBSCRIPTION_RULE_NO = DEFAULT_SUBSCRIPTION_RULE_NO


class SubscriptionPurchaseRequest(BaseModel):
    rule_no: int = Field(default=SUBSCRIPTION_RULE_NO)


# ============================================================
# INTERNAL COIN HELPERS
# ============================================================


def _get_owner_business(cursor, user_id: int) -> dict:
    """Return the first business belonging to an authenticated owner."""
    cursor.execute(
        """
        SELECT business_id, business_name
        FROM business_info
        WHERE user_id = %s
        ORDER BY business_id ASC
        LIMIT 1
        """,
        (user_id,),
    )

    row = cursor.fetchone()

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Business profile not found.",
        )

    return row


def _resolve_rule(rule_no: int) -> dict:
    """Validate and return one configured coin rule."""
    try:
        rule_no = int(rule_no)
    except (TypeError, ValueError) as error:
        raise HTTPException(
            status_code=400,
            detail="Invalid coin rule number.",
        ) from error

    rule = COIN_TRANSACTION_RULES.get(rule_no)

    if not rule:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported coin rule: {rule_no}.",
        )

    return rule


def _resolve_rule_owner(
    cursor,
    *,
    user_id: int | None = None,
    business_id: int | None = None,
    dashboard_id: int | None = None,
) -> tuple[int, int]:
    """Resolve the business owner safely for a coin operation.

    Public customer flows may provide dashboard_id instead of user_id.
    Authenticated owner flows provide user_id/business_id.
    """
    if dashboard_id is not None:
        cursor.execute(
            """
            SELECT user_id, business_id
            FROM dashboard
            WHERE dashboard_id = %s
            LIMIT 1
            """,
            (dashboard_id,),
        )

        dashboard = cursor.fetchone()

        if not dashboard:
            raise HTTPException(
                status_code=404,
                detail="Dashboard not found.",
            )

        return int(dashboard["user_id"]), int(dashboard["business_id"])

    if user_id is None:
        raise HTTPException(
            status_code=401,
            detail="Coin operation owner could not be identified.",
        )

    if business_id is None:
        business = _get_owner_business(cursor, int(user_id))
        business_id = int(business["business_id"])

    # Do not trust a business_id supplied by a caller without checking ownership.
    cursor.execute(
        """
        SELECT business_id
        FROM business_info
        WHERE business_id = %s
          AND user_id = %s
        LIMIT 1
        """,
        (business_id, user_id),
    )

    business = cursor.fetchone()

    if not business:
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this business coin balance.",
        )

    return int(user_id), int(business_id)


def _get_balance_row(
    cursor,
    user_id: int,
    business_id: int,
    lock: bool = False,
) -> dict | None:
    """Read the wallet row, optionally locking it for the current transaction."""
    query = """
        SELECT
            coin_balance_id,
            user_id,
            business_id,
            coin_balance,
            updates_at
        FROM coin_balance
        WHERE user_id = %s
          AND business_id = %s
        LIMIT 1
    """

    if lock:
        query += " FOR UPDATE"

    cursor.execute(query, (user_id, business_id))
    return cursor.fetchone()


def _ensure_balance_row(cursor, user_id: int, business_id: int) -> dict:
    """Create the wallet when necessary and return its locked row."""
    row = _get_balance_row(
        cursor,
        user_id,
        business_id,
        lock=True,
    )

    if row:
        return row

    try:
        cursor.execute(
            """
            INSERT INTO coin_balance
            (
                user_id,
                business_id,
                coin_balance
            )
            VALUES (%s, %s, 0)
            """,
            (user_id, business_id),
        )
    except Exception as error:
        # A concurrent request may have created the unique wallet row.
        # The caller's outer transaction will roll back on a real failure.
        raise RuntimeError(
            f"Unable to initialize coin balance: {error}"
        ) from error

    row = _get_balance_row(
        cursor,
        user_id,
        business_id,
        lock=True,
    )

    if not row:
        raise RuntimeError("Coin balance could not be initialized.")

    return row


def _get_subscription_rule_no(subscription: dict) -> int | None:
    """Resolve the configured rule number represented by a history row.

    The current database schema stores the selected membership as text in
    `subscription_taken_rule`, not as a separate rule-number column. New
    purchases store a stable `Rule <number> - ...` value, while this helper
    also understands the existing Rule-3 history format for compatibility.
    """
    if not subscription:
        return None

    raw_value = str(subscription.get("subscription_taken_rule") or "").strip()

    # Preferred format: "Rule 4 - Yearly unlimited membership".
    if raw_value.lower().startswith("rule "):
        parts = raw_value.split(maxsplit=2)
        if len(parts) >= 2:
            try:
                candidate = int(parts[1])
            except ValueError:
                candidate = None

            if candidate in COIN_TRANSACTION_RULES:
                rule = COIN_TRANSACTION_RULES[candidate]
                if rule["type"] == "subscription":
                    return candidate

    # Compatibility with any older rows that may contain only the
    # configured code or name.
    normalized = raw_value.casefold()
    for candidate, rule in COIN_TRANSACTION_RULES.items():
        if rule["type"] != "subscription":
            continue
        if normalized in {
            str(rule["code"]).casefold(),
            str(rule["name"]).casefold(),
        }:
            return int(candidate)

    return None


def _get_active_subscription(cursor, coin_balance_id: int) -> dict | None:
    """Return the latest active subscription entitlement, if any."""
    cursor.execute(
        """
        SELECT
            coin_subscription_history_id,
            coin_balance_id,
            subscription_taken_rule,
            updated_at,
            expires_at
        FROM coin_subscription_history
        WHERE coin_balance_id = %s
          AND expires_at > CURRENT_TIMESTAMP
        ORDER BY expires_at DESC, coin_subscription_history_id DESC
        LIMIT 1
        """,
        (coin_balance_id,),
    )

    subscription = cursor.fetchone()

    if not subscription:
        return None

    subscription["rule_no"] = _get_subscription_rule_no(subscription)
    return subscription


def _subscription_covers_usage(
    subscription: dict | None,
    usage_rule_no: int,
) -> bool:
    """Return whether an active membership covers a usage rule."""
    if not subscription:
        return False

    subscription_rule_no = subscription.get("rule_no")
    if subscription_rule_no is None:
        # Never grant a free entitlement when an existing legacy row cannot
        # be mapped safely to a configured subscription rule.
        return False

    subscription_rule = _resolve_rule(int(subscription_rule_no))
    if subscription_rule["type"] != "subscription":
        return False

    return int(usage_rule_no) in {
        int(rule_no)
        for rule_no in subscription_rule.get("included_usage_rules", [])
    }


def _record_coin_transaction(
    cursor,
    *,
    coin_balance_id: int,
    rule_no: int,
    coins: int,
    balance_before: int,
    balance_after: int,
    reference_id: int | None,
    transaction_type: str = "debit",
) -> int:
    """Write the immutable transaction ledger entry."""
    rule = _resolve_rule(rule_no)

    cursor.execute(
        """
        INSERT INTO coin_transaction_history
        (
            coin_balance_id,
            transaction_type,
            rule_no,
            coins,
            balance_before,
            balance_after,
            reference_id,
            description,
            created_at
        )
        VALUES
        (
            %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP
        )
        """,
        (
            coin_balance_id,
            transaction_type,
            rule_no,
            coins,
            balance_before,
            balance_after,
            reference_id,
            rule["description"],
        ),
    )

    return int(cursor.lastrowid)


def _deduct_usage_rule(
    cursor,
    *,
    rule: dict,
    user_id: int,
    business_id: int,
    reference_id: int | None,
) -> dict:
    """Execute a normal billable usage rule such as Review or Website."""
    balance = _ensure_balance_row(
        cursor,
        user_id,
        business_id,
    )

    coin_balance_id = int(balance["coin_balance_id"])
    current_balance = int(balance["coin_balance"] or 0)

    # An active membership is an entitlement. Only skip the usage debit
    # when the selected membership explicitly includes this usage rule.
    subscription = _get_active_subscription(
        cursor,
        coin_balance_id,
    )

    if _subscription_covers_usage(
        subscription,
        int(rule["rule_no"]),
    ):
        return {
            "charged": False,
            "subscription_active": True,
            "rule_no": int(rule["rule_no"]),
            "coins_charged": 0,
            "coin_balance": current_balance,
            "transaction_id": None,
        }

    cost = int(rule["coins"])

    if current_balance < cost:
        raise HTTPException(
            status_code=402,
            detail=(
                f"Insufficient coins. Rule {rule['rule_no']} requires "
                f"{cost} coin(s), but your current balance is "
                f"{current_balance}."
            ),
        )

    new_balance = current_balance - cost

    cursor.execute(
        """
        UPDATE coin_balance
        SET
            coin_balance = %s,
            updates_at = CURRENT_TIMESTAMP
        WHERE coin_balance_id = %s
        """,
        (
            new_balance,
            coin_balance_id,
        ),
    )

    transaction_id = _record_coin_transaction(
        cursor,
        coin_balance_id=coin_balance_id,
        rule_no=int(rule["rule_no"]),
        coins=cost,
        balance_before=current_balance,
        balance_after=new_balance,
        reference_id=reference_id,
    )

    return {
        "charged": True,
        "subscription_active": False,
        "rule_no": int(rule["rule_no"]),
        "coins_charged": cost,
        "coin_balance": new_balance,
        "transaction_id": transaction_id,
    }


def _purchase_subscription_rule(
    cursor,
    *,
    rule: dict,
    user_id: int,
    business_id: int,
    reference_id: int | None,
) -> dict:
    """Purchase any configured subscription rule atomically."""
    balance = _ensure_balance_row(
        cursor,
        user_id,
        business_id,
    )

    coin_balance_id = int(balance["coin_balance_id"])
    current_balance = int(balance["coin_balance"] or 0)

    active = _get_active_subscription(
        cursor,
        coin_balance_id,
    )

    if active:
        active_rule_no = active.get("rule_no")
        active_rule = (
            _resolve_rule(int(active_rule_no))
            if active_rule_no is not None
            else None
        )
        active_name = (
            active_rule["name"]
            if active_rule
            else "an active membership"
        )

        raise HTTPException(
            status_code=409,
            detail=f"Your {active_name.lower()} is already active.",
        )

    cost = int(rule["coins"])

    if current_balance < cost:
        raise HTTPException(
            status_code=402,
            detail=(
                f"Insufficient coins. Membership requires {cost} coins, "
                f"but your current balance is {current_balance}."
            ),
        )

    new_balance = current_balance - cost

    # Application time is created only through main.py.
    # MySQL stores the explicit expiry as a naive UTC TIMESTAMP.
    expires_at = now_utc() + timedelta(
        days=int(rule["duration_days"])
    )
    expires_at_db = expires_at.replace(tzinfo=None)

    cursor.execute(
        """
        UPDATE coin_balance
        SET
            coin_balance = %s,
            updates_at = CURRENT_TIMESTAMP
        WHERE coin_balance_id = %s
        """,
        (
            new_balance,
            coin_balance_id,
        ),
    )

    cursor.execute(
        """
        INSERT INTO coin_subscription_history
        (
            coin_balance_id,
            subscription_taken_rule,
            updated_at,
            expires_at
        )
        VALUES
        (
            %s,
            %s,
            CURRENT_TIMESTAMP,
            %s
        )
        """,
        (
            coin_balance_id,
            f"Rule {int(rule['rule_no'])} - {rule['name']}",
            expires_at_db,
        ),
    )

    subscription_history_id = int(cursor.lastrowid)

    transaction_id = _record_coin_transaction(
        cursor,
        coin_balance_id=coin_balance_id,
        rule_no=int(rule["rule_no"]),
        coins=cost,
        balance_before=current_balance,
        balance_after=new_balance,
        reference_id=(
            reference_id
            if reference_id is not None
            else subscription_history_id
        ),
    )

    return {
        "charged": True,
        "subscription_active": True,
        "rule_no": int(rule["rule_no"]),
        "coins_charged": cost,
        "coin_balance": new_balance,
        "transaction_id": transaction_id,
        "subscription_history_id": subscription_history_id,
        "expires_at": serialize_datetime(expires_at),
    }



# ============================================================
# SINGLE PUBLIC COIN RULE FUNCTION
# ============================================================


def _preflight_usage_rule(
    cursor,
    *,
    rule: dict,
    user_id: int,
    business_id: int,
) -> dict:
    """Check entitlement before expensive work without mutating the wallet.

    This is intentionally private. Feature modules never call it directly.
    The public ``authorize_usage`` API exposes the preflight phase.
    """
    if rule["type"] != "usage":
        raise HTTPException(
            status_code=400,
            detail=(
                f"Rule {rule['rule_no']} is not a usage rule and cannot be "
                "preflight-authorized."
            ),
        )

    # Read-only lookup. Do not create or lock a wallet during preflight.
    balance = _get_balance_row(
        cursor,
        user_id,
        business_id,
        lock=False,
    )

    current_balance = (
        int(balance["coin_balance"] or 0)
        if balance
        else 0
    )

    subscription = None

    if balance:
        subscription = _get_active_subscription(
            cursor,
            int(balance["coin_balance_id"]),
        )

    if _subscription_covers_usage(
        subscription,
        int(rule["rule_no"]),
    ):
        return {
            "authorized": True,
            "phase": "preflight",
            "charged": False,
            "subscription_active": True,
            "rule_no": int(rule["rule_no"]),
            "required_coins": int(rule["coins"]),
            "coin_balance": current_balance,
        }

    cost = int(rule["coins"])

    if current_balance < cost:
        raise HTTPException(
            status_code=402,
            detail=(
                f"Insufficient coins. Rule {rule['rule_no']} requires "
                f"{cost} coin(s), but your current balance is "
                f"{current_balance}."
            ),
        )

    return {
        "authorized": True,
        "phase": "preflight",
        "charged": False,
        "subscription_active": False,
        "rule_no": int(rule["rule_no"]),
        "required_coins": cost,
        "coin_balance": current_balance,
    }


def authorize_usage(
    cursor,
    *,
    rule_no: int,
    user_id: int | None = None,
    business_id: int | None = None,
    dashboard_id: int | None = None,
    reference_id: int | None = None,
    phase: str = "finalize",
) -> dict:
    """Authorize one configured billing rule through the single coin API.

    ``phase="preflight"`` performs a read-only entitlement/balance check and
    raises HTTP 402 before expensive feature work when the account cannot
    afford the operation.

    ``phase="finalize"`` performs the authoritative wallet-locked check and,
    for usage rules, deducts coins. Feature DB writes and this final billing
    operation must be committed in the same database transaction.

    Feature modules must never call private coin helpers directly or implement
    their own balance, membership, 402, wallet, or deduction logic.

    Examples:

        authorize_usage(
            cursor=cursor,
            rule_no=1,
            dashboard_id=dashboard_id,
            reference_id=review_id,
        )

        authorize_usage(
            cursor=cursor,
            rule_no=2,
            user_id=user_id,
            business_id=business_id,
            reference_id=website_version_id,
        )

        authorize_usage(
            cursor=cursor,
            rule_no=3,
            user_id=user_id,
            business_id=business_id,
        )

    The caller owns the surrounding database transaction. Therefore:

        business INSERTs
            +
        authorize_usage(...)
            +
        db.commit()

    are committed together. Any HTTPException or unexpected error causes
    the caller's existing rollback handling to undo the entire operation.
    """
    phase = str(phase or "finalize").strip().lower()

    if phase not in {"preflight", "finalize"}:
        raise HTTPException(
            status_code=400,
            detail="Invalid billing phase. Use 'preflight' or 'finalize'.",
        )

    rule = _resolve_rule(rule_no)

    resolved_user_id, resolved_business_id = _resolve_rule_owner(
        cursor,
        user_id=user_id,
        business_id=business_id,
        dashboard_id=dashboard_id,
    )

    if phase == "preflight":
        if rule["type"] != "usage":
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Rule {rule_no} is not a usage rule and cannot be "
                    "preflight-authorized."
                ),
            )

        return _preflight_usage_rule(
            cursor,
            rule=rule,
            user_id=resolved_user_id,
            business_id=resolved_business_id,
        )

    if rule["type"] == "usage":
        return _deduct_usage_rule(
            cursor,
            rule=rule,
            user_id=resolved_user_id,
            business_id=resolved_business_id,
            reference_id=reference_id,
        )

    if rule["type"] == "subscription":
        return _purchase_subscription_rule(
            cursor,
            rule=rule,
            user_id=resolved_user_id,
            business_id=resolved_business_id,
            reference_id=reference_id,
        )

    raise HTTPException(
        status_code=500,
        detail=f"Coin rule {rule_no} has an unsupported type.",
    )


def apply_coin_rule(
    cursor,
    *,
    rule_no: int,
    user_id: int | None = None,
    business_id: int | None = None,
    dashboard_id: int | None = None,
    reference_id: int | None = None,
    phase: str = "finalize",
) -> dict:
    """Backward-compatible alias for :func:`authorize_usage`.

    Existing feature routes can continue using this name during migration.
    New feature code should call ``authorize_usage`` directly.
    """
    return authorize_usage(
        cursor=cursor,
        rule_no=rule_no,
        user_id=user_id,
        business_id=business_id,
        dashboard_id=dashboard_id,
        reference_id=reference_id,
        phase=phase,
    )


# ============================================================
# CURRENT BALANCE
# ============================================================


@router.get("/balance")
def get_coin_balance(user_id: int = Depends(get_current_user_id)):
    db = None
    cursor = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        business = _get_owner_business(cursor, user_id)
        row = _get_balance_row(cursor, user_id, int(business["business_id"]))
        return {
            "success": True,
            "business_id": int(business["business_id"]),
            "coin_balance_id": int(row["coin_balance_id"]) if row else None,
            "coin_balance": int(row["coin_balance"] or 0) if row else 0,
            "updates_at": serialize_datetime(row["updates_at"]) if row else None,
        }
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


# ============================================================
# COIN MANAGEMENT POPUP DATA
# ============================================================


@router.get("/management")
def get_coin_management(user_id: int = Depends(get_current_user_id)):
    db = None
    cursor = None
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        business = _get_owner_business(cursor, user_id)
        business_id = int(business["business_id"])
        balance = _get_balance_row(cursor, user_id, business_id)
        balance_id = int(balance["coin_balance_id"]) if balance else None
        current_balance = int(balance["coin_balance"] or 0) if balance else 0

        subscription = _get_active_subscription(cursor, balance_id) if balance_id else None

        history = []
        if balance_id:
            cursor.execute(
                """
                SELECT
                    coin_transaction_history_id,
                    transaction_type,
                    rule_no,
                    coins,
                    balance_before,
                    balance_after,
                    reference_id,
                    description,
                    created_at
                FROM coin_transaction_history
                WHERE coin_balance_id = %s
                ORDER BY coin_transaction_history_id DESC
                LIMIT 20
                """,
                (balance_id,),
            )
            history = cursor.fetchall() or []

        subscription_history = []
        if balance_id:
            cursor.execute(
                """
                SELECT
                    coin_subscription_history_id,
                    coin_balance_id,
                    subscription_taken_rule,
                    updated_at,
                    expires_at
                FROM coin_subscription_history
                WHERE coin_balance_id = %s
                ORDER BY coin_subscription_history_id DESC
                LIMIT 20
                """,
                (balance_id,),
            )
            subscription_history = cursor.fetchall() or []

        return {
            "success": True,
            "business": business,
            "coin_balance": current_balance,
            "subscription": {
                "active": bool(subscription),
                "rule_no": subscription.get("rule_no") if subscription else None,
                "code": (
                    COIN_TRANSACTION_RULES[int(subscription["rule_no"])]["code"]
                    if subscription and subscription.get("rule_no") in COIN_TRANSACTION_RULES
                    else None
                ),
                "name": (
                    COIN_TRANSACTION_RULES[int(subscription["rule_no"])]["name"]
                    if subscription and subscription.get("rule_no") in COIN_TRANSACTION_RULES
                    else None
                ),
                "subscription_taken_rule": subscription["subscription_taken_rule"] if subscription else None,
                "updated_at": serialize_datetime(subscription["updated_at"]) if subscription else None,
                "expires_at": serialize_datetime(subscription["expires_at"]) if subscription else None,
            },
            # Keep usage rules and membership plans separately structured.
            # The frontend can render configured plans without hardcoding
            # billing prices or durations.
            "usage_rules": [
                rule
                for rule in COIN_TRANSACTION_RULES.values()
                if rule["type"] == "usage"
            ],
            "subscription_plans": [
                rule
                for rule in COIN_TRANSACTION_RULES.values()
                if rule["type"] == "subscription"
            ],
            # Backward-compatible complete rule registry.
            "rules": list(COIN_TRANSACTION_RULES.values()),
            "transactions": [
                {
                    **item,
                    "coins": int(item["coins"]),
                    "balance_before": int(item["balance_before"]),
                    "balance_after": int(item["balance_after"]),
                    "created_at": serialize_datetime(item["created_at"]),
                }
                for item in history
            ],
            "subscription_history": [
                {
                    **item,
                    "updated_at": serialize_datetime(item["updated_at"]),
                    "expires_at": serialize_datetime(item["expires_at"]),
                }
                for item in subscription_history
            ],
        }
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


# ============================================================
# PURCHASE MEMBERSHIP USING COINS
# ============================================================


@router.post("/subscription/purchase")
def purchase_subscription(
    payload: SubscriptionPurchaseRequest,
    user_id: int = Depends(get_current_user_id),
):
    """Purchase any configured subscription through the central billing engine."""
    rule = _resolve_rule(payload.rule_no)

    if rule["type"] != "subscription":
        raise HTTPException(
            status_code=400,
            detail=f"Rule {payload.rule_no} is not a subscription rule.",
        )

    db = None
    cursor = None

    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        business = _get_owner_business(cursor, user_id)
        business_id = int(business["business_id"])

        result = authorize_usage(
            cursor=cursor,
            rule_no=payload.rule_no,
            user_id=user_id,
            business_id=business_id,
        )

        db.commit()

        return {
            "success": True,
            "message": f"{rule['name']} activated successfully.",
            "rule_no": int(rule["rule_no"]),
            "rule_code": rule["code"],
            "rule_name": rule["name"],
            "coin_balance": result["coin_balance"],
            "subscription_history_id": result.get("subscription_history_id"),
            "transaction_id": result.get("transaction_id"),
            "expires_at": result.get("expires_at"),
        }

    except HTTPException:
        if db:
            db.rollback()
        raise

    except Exception as error:
        if db:
            db.rollback()

        print(f"Subscription purchase error: {error}")

        raise HTTPException(
            status_code=500,
            detail="Unable to activate membership.",
        ) from error

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()
