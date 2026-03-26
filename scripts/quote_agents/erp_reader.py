import sqlite3
from typing import Any


def connect_external_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def get_parts_pricing_context(conn: sqlite3.Connection, normalized_part_number: str) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT
          model,
          st_official_price_usd,
          agent_price_usd,
          recent_orders,
          lc_price_usd_ex_tax,
          lc_price_cny_tax,
          usd_fx_rate,
          tax_factor
        FROM parts_pricing
        WHERE model=?
        ORDER BY rowid DESC
        LIMIT 1
        """,
        (normalized_part_number,),
    ).fetchone()
    if row is None:
        return {
            "parts_pricing_found": False,
            "parts_pricing_floor_price": None,
            "parts_pricing_normal_price": None,
            "parts_recent_orders": None,
            "parts_market_proxy_price": None,
            "parts_internal_notes": "no parts_pricing row found",
        }
    if row is None:
        return {}
    data = dict(row)
    return {
        "parts_pricing_found": True,
        "parts_pricing_floor_price": data.get("st_official_price_usd"),
        "parts_pricing_normal_price": data.get("agent_price_usd"),
        "parts_recent_orders": data.get("recent_orders"),
        "parts_market_proxy_price": data.get("lc_price_usd_ex_tax"),
        "parts_internal_notes": "derived from sol.db parts_pricing",
    }


def get_erp_inventory_context(conn: sqlite3.Connection, normalized_part_number: str) -> dict[str, Any]:
    if not table_exists(conn, "erp_inventory"):
        return {
            "erp_inventory_found": False,
            "erp_inventory_floor_price": None,
            "erp_inventory_standard_price": None,
            "erp_inventory_taxed_sale_price": None,
            "erp_inventory_stock_qty": None,
            "erp_inventory_supply_status": None,
            "erp_inventory_package_type": None,
            "erp_inventory_notes": "erp_inventory table missing",
        }
    row = conn.execute(
        """
        SELECT
          model,
          stock_qty,
          floor_sale_price,
          taxed_sale_price,
          standard_sale_price,
          package_type,
          supply_status,
          inbound_date,
          warehouse,
          import_batch_id
        FROM erp_inventory
        WHERE model=?
        ORDER BY
          CASE WHEN stock_qty IS NULL THEN 1 ELSE 0 END,
          stock_qty DESC,
          erp_inventory_id DESC
        LIMIT 1
        """,
        (normalized_part_number,),
    ).fetchone()
    if row is None:
        return {
            "erp_inventory_found": False,
            "erp_inventory_floor_price": None,
            "erp_inventory_standard_price": None,
            "erp_inventory_taxed_sale_price": None,
            "erp_inventory_stock_qty": None,
            "erp_inventory_supply_status": None,
            "erp_inventory_package_type": None,
            "erp_inventory_notes": "no erp_inventory row found",
        }
    data = dict(row)
    return {
        "erp_inventory_found": True,
        "erp_inventory_floor_price": data.get("floor_sale_price"),
        "erp_inventory_standard_price": data.get("standard_sale_price"),
        "erp_inventory_taxed_sale_price": data.get("taxed_sale_price"),
        "erp_inventory_stock_qty": data.get("stock_qty"),
        "erp_inventory_supply_status": data.get("supply_status"),
        "erp_inventory_package_type": data.get("package_type"),
        "erp_inventory_inbound_date": data.get("inbound_date"),
        "erp_inventory_warehouse": data.get("warehouse"),
        "erp_inventory_import_batch_id": data.get("import_batch_id"),
        "erp_inventory_notes": "derived from imported ERP workbook",
    }


def get_soq_product_context(soq_conn: sqlite3.Connection, normalized_part_number: str) -> dict[str, Any]:
    if not table_exists(soq_conn, "products"):
        return {
            "soq_product_found": False,
            "soq_normal_price": None,
            "soq_floor_price": None,
            "soq_min_auto_accept_price": None,
            "soq_default_supply_type": None,
            "soq_internal_notes": "products table missing",
        }
    row = soq_conn.execute(
        """
        SELECT
          model,
          normal_price,
          floor_price,
          min_auto_accept_price,
          default_supply_type,
          active
        FROM products
        WHERE model=? AND active=1
        LIMIT 1
        """,
        (normalized_part_number,),
    ).fetchone()
    if row is None:
        return {
            "soq_product_found": False,
            "soq_normal_price": None,
            "soq_floor_price": None,
            "soq_min_auto_accept_price": None,
            "soq_default_supply_type": None,
            "soq_internal_notes": "no soq products row found",
        }
    data = dict(row)
    return {
        "soq_product_found": True,
        "soq_normal_price": data.get("normal_price"),
        "soq_floor_price": data.get("floor_price"),
        "soq_min_auto_accept_price": data.get("min_auto_accept_price"),
        "soq_default_supply_type": data.get("default_supply_type"),
        "soq_internal_notes": "derived from qq soq.db products",
    }


def get_customer_context(soq_conn: sqlite3.Connection, customer_id: str | None = None) -> dict[str, Any]:
    if not customer_id:
        return {
            "customer_found": False,
            "customer_tier": None,
            "customer_style": None,
            "allow_floor_strategy": None,
            "customer_notes": "customer_id not provided",
        }
    if not table_exists(soq_conn, "customers"):
        return {
            "customer_found": False,
            "customer_tier": None,
            "customer_style": None,
            "allow_floor_strategy": None,
            "customer_notes": "customers table missing",
        }
    row = soq_conn.execute(
        """
        SELECT
          customer_id,
          level,
          price_sensitivity_score,
          allow_floor_strategy,
          notes
        FROM customers
        WHERE customer_id=?
        LIMIT 1
        """,
        (customer_id,),
    ).fetchone()
    if row is None:
        return {
            "customer_found": False,
            "customer_tier": None,
            "customer_style": None,
            "allow_floor_strategy": None,
            "customer_notes": "no customer row found",
        }
    data = dict(row)
    score = data.get("price_sensitivity_score")
    style = None
    if score is not None:
        style = "price_sensitive" if float(score) >= 0.7 else "normal"
    return {
        "customer_found": True,
        "customer_tier": data.get("level"),
        "customer_style": style,
        "allow_floor_strategy": data.get("allow_floor_strategy"),
        "customer_notes": data.get("notes"),
    }


def get_last_deal_context(soq_conn: sqlite3.Connection, normalized_part_number: str, customer_id: str | None = None) -> dict[str, Any]:
    if not table_exists(soq_conn, "soq_logs"):
        return {
            "last_deal_price": None,
            "last_deal_conversation_id": None,
            "last_deal_at": None,
            "last_deal_notes": "soq_logs table missing",
        }
    sql = """
    SELECT
      conversation_id,
      quoted_price,
      created_at,
      action_taken
    FROM soq_logs
    WHERE parsed_model=? AND quoted_price IS NOT NULL
    """
    params: list[Any] = [normalized_part_number]
    if customer_id:
        sql += " AND customer_id=?"
        params.append(customer_id)
    sql += " ORDER BY id DESC LIMIT 1"
    row = soq_conn.execute(sql, tuple(params)).fetchone()
    if row is None:
        return {
            "last_deal_price": None,
            "last_deal_conversation_id": None,
            "last_deal_at": None,
            "last_deal_notes": "no quoted history found in soq_logs",
        }
    data = dict(row)
    return {
        "last_deal_price": data.get("quoted_price"),
        "last_deal_conversation_id": data.get("conversation_id"),
        "last_deal_at": data.get("created_at"),
        "last_deal_notes": f"derived from soq_logs action={data.get('action_taken')}",
    }


def get_erp_context(
    conn: sqlite3.Connection,
    normalized_part_number: str,
    customer_id: str | None = None,
    soq_db_path: str = r"F:/Jay_ic_tw/qq/agent-harness/soq.db",
) -> dict[str, Any]:
    inventory_ctx = get_erp_inventory_context(conn, normalized_part_number)
    parts_ctx = get_parts_pricing_context(conn, normalized_part_number)
    soq_conn = connect_external_db(soq_db_path)
    try:
        product_ctx = get_soq_product_context(soq_conn, normalized_part_number)
        customer_ctx = get_customer_context(soq_conn, customer_id=customer_id)
        last_deal_ctx = get_last_deal_context(soq_conn, normalized_part_number, customer_id=customer_id)
    finally:
        soq_conn.close()

    floor_candidates = [
        inventory_ctx.get("erp_inventory_floor_price"),
        product_ctx.get("soq_floor_price"),
        parts_ctx.get("parts_pricing_floor_price"),
    ]
    normal_candidates = [
        inventory_ctx.get("erp_inventory_standard_price"),
        product_ctx.get("soq_normal_price"),
        parts_ctx.get("parts_pricing_normal_price"),
    ]
    erp_floor_price = next((value for value in floor_candidates if value not in (None, "")), None)
    erp_normal_price = next((value for value in normal_candidates if value not in (None, "")), None)
    erp_found = any(
        [
            inventory_ctx.get("erp_inventory_found"),
            parts_ctx.get("parts_pricing_found"),
            product_ctx.get("soq_product_found"),
        ]
    )
    note_parts = [
        inventory_ctx.get("erp_inventory_notes"),
        parts_ctx.get("parts_internal_notes"),
        product_ctx.get("soq_internal_notes"),
        customer_ctx.get("customer_notes"),
        last_deal_ctx.get("last_deal_notes"),
    ]
    internal_notes = " | ".join(str(x) for x in note_parts if x)

    return {
        "erp_found": erp_found,
        "erp_floor_price": erp_floor_price,
        "erp_normal_price": erp_normal_price,
        "erp_taxed_sale_price": inventory_ctx.get("erp_inventory_taxed_sale_price"),
        "min_auto_accept_price": product_ctx.get("soq_min_auto_accept_price"),
        "last_deal_price": last_deal_ctx.get("last_deal_price"),
        "last_deal_conversation_id": last_deal_ctx.get("last_deal_conversation_id"),
        "last_deal_at": last_deal_ctx.get("last_deal_at"),
        "customer_tier": customer_ctx.get("customer_tier"),
        "customer_style": customer_ctx.get("customer_style"),
        "allow_floor_strategy": customer_ctx.get("allow_floor_strategy"),
        "default_supply_type": product_ctx.get("soq_default_supply_type"),
        "erp_inventory_stock_qty": inventory_ctx.get("erp_inventory_stock_qty"),
        "erp_inventory_supply_status": inventory_ctx.get("erp_inventory_supply_status"),
        "erp_inventory_package_type": inventory_ctx.get("erp_inventory_package_type"),
        "erp_inventory_inbound_date": inventory_ctx.get("erp_inventory_inbound_date"),
        "erp_inventory_warehouse": inventory_ctx.get("erp_inventory_warehouse"),
        "parts_recent_orders": parts_ctx.get("parts_recent_orders"),
        "parts_market_proxy_price": parts_ctx.get("parts_market_proxy_price"),
        "erp_inventory_found": inventory_ctx.get("erp_inventory_found"),
        "soq_product_found": product_ctx.get("soq_product_found"),
        "parts_pricing_found": parts_ctx.get("parts_pricing_found"),
        "customer_found": customer_ctx.get("customer_found"),
        "internal_notes": internal_notes or "no ERP or SOQ detail found",
    }
