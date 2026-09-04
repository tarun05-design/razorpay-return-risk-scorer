"""
features.py
-----------
Every feature here must be knowable at (or very shortly after) order
placement — a scorer that peeks at delivery outcomes or review text is
useless in production and would inflate offline metrics dishonestly.

The one feature that needs care is "seller's historical bad-order rate":
if computed globally (using ALL of a seller's orders, including ones that
happen chronologically AFTER the order being scored), it leaks the future
into the past. We compute it as an EXPANDING window ordered by purchase
timestamp, so a seller's prior orders inform later scores, never the
reverse. New sellers with no history fall back to the global base rate
(shrinkage), which also fixes the small-sample-size problem for sellers
with 1-2 past orders.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _distance_flag(customer_state: pd.Series, seller_state: pd.Series) -> pd.Series:
    return (customer_state != seller_state).astype(int)


def build_order_level_table(
    orders: pd.DataFrame,
    items: pd.DataFrame,
    payments: pd.DataFrame,
    products: pd.DataFrame,
    sellers: pd.DataFrame,
    customers: pd.DataFrame,
    category_translation: pd.DataFrame,
) -> pd.DataFrame:
    """Collapse the multi-table Olist schema into one row per order_id with
    only pre-outcome fields."""

    orders = orders.copy()
    orders["order_purchase_timestamp"] = pd.to_datetime(orders["order_purchase_timestamp"])
    orders["order_estimated_delivery_date"] = pd.to_datetime(orders["order_estimated_delivery_date"])

    items = items.merge(products, on="product_id", how="left")
    items = items.merge(category_translation, on="product_category_name", how="left")
    items = items.merge(sellers[["seller_id", "seller_state"]], on="seller_id", how="left")

    # item-level aggregation -> per order
    item_agg = items.groupby("order_id").agg(
        n_items=("order_item_id", "count"),
        n_distinct_products=("product_id", "nunique"),
        n_distinct_sellers=("seller_id", "nunique"),
        total_price=("price", "sum"),
        total_freight=("freight_value", "sum"),
        avg_price=("price", "mean"),
        max_price=("price", "max"),
        avg_weight_g=("product_weight_g", "mean"),
        avg_photos_qty=("product_photos_qty", "mean"),
        avg_desc_length=("product_description_lenght", "mean"),
        avg_name_length=("product_name_lenght", "mean"),
    ).reset_index()

    # dominant category & dominant seller per order (first item, simplest defensible choice)
    first_item = items.sort_values("order_item_id").drop_duplicates("order_id", keep="first")
    item_agg = item_agg.merge(
        first_item[["order_id", "product_category_name_english", "seller_id", "seller_state"]],
        on="order_id",
        how="left",
    )

    # payments
    pay_agg = payments.groupby("order_id").agg(
        n_payment_installments=("payment_installments", "max"),
        total_payment_value=("payment_value", "sum"),
        n_payment_methods=("payment_type", "nunique"),
    ).reset_index()
    dominant_payment_type = (
        payments.sort_values("payment_value", ascending=False)
        .drop_duplicates("order_id", keep="first")[["order_id", "payment_type"]]
    )
    pay_agg = pay_agg.merge(dominant_payment_type, on="order_id", how="left")

    # customer state
    orders = orders.merge(customers[["customer_id", "customer_state"]], on="customer_id", how="left")

    df = (
        orders[[
            "order_id", "order_status", "order_purchase_timestamp",
            "order_estimated_delivery_date", "customer_state",
        ]]
        .merge(item_agg, on="order_id", how="left")
        .merge(pay_agg, on="order_id", how="left")
    )

    df["promised_delivery_days"] = (
        df["order_estimated_delivery_date"] - df["order_purchase_timestamp"]
    ).dt.days

    df["purchase_dow"] = df["order_purchase_timestamp"].dt.dayofweek
    df["purchase_hour"] = df["order_purchase_timestamp"].dt.hour
    df["purchase_month"] = df["order_purchase_timestamp"].dt.month

    df["is_interstate"] = _distance_flag(df["customer_state"], df["seller_state"])
    df["freight_to_price_ratio"] = df["total_freight"] / df["total_price"].replace(0, np.nan)
    df["price_per_item"] = df["total_price"] / df["n_items"].replace(0, np.nan)
    df["is_multi_item"] = (df["n_items"] > 1).astype(int)
    df["is_multi_seller"] = (df["n_distinct_sellers"] > 1).astype(int)
    df["high_installments"] = (df["n_payment_installments"].fillna(0) >= 6).astype(int)

    return df


def add_expanding_seller_prior(
    df: pd.DataFrame,
    labels: pd.DataFrame,
    global_base_rate: float,
    min_prior_orders_for_trust: int = 20,
) -> pd.DataFrame:
    """Adds `seller_prior_bad_rate`: an expanding (time-ordered), leakage-safe
    estimate of how often this seller's PAST labeled orders were return-risk.
    Shrinks toward the global base rate when the seller has little history.
    """
    df = df.merge(labels[["order_id", "return_risk"]], on="order_id", how="left")
    df = df.sort_values("order_purchase_timestamp").reset_index(drop=True)

    df["_is_labeled"] = df["return_risk"].notna().astype(int)
    df["_label_val"] = df["return_risk"].fillna(0)

    grp = df.groupby("seller_id", sort=False)
    cum_bad = grp["_label_val"].cumsum() - df["_label_val"]
    cum_n = grp["_is_labeled"].cumsum() - df["_is_labeled"]

    # shrinkage toward global base rate for sellers with thin history
    k = min_prior_orders_for_trust
    df["seller_prior_bad_rate"] = (cum_bad + k * global_base_rate) / (cum_n + k)
    df["seller_prior_n_orders"] = cum_n

    df = df.drop(columns=["_is_labeled", "_label_val", "return_risk"])
    return df
