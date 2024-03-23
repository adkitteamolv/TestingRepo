from datetime import timedelta

import pandas as pd
import yaml

from feast import (
    Entity,
    FeatureService,
    FeatureView,
    Field,
    PushSource,
    RequestSource,
    SnowflakeSource,
    batch_feature_view,
    aggregation
)
from feast.on_demand_feature_view import on_demand_feature_view
from feast.types import Float32, Float64, Int64, String, UnixTimestamp
import numpy as np
from datetime import datetime, timedelta

# Define an entity for the Customer_id. You can think of an entity as a primary key used to
# fetch features.
customer = Entity(name="customer", join_keys=["CUSTOMER_ID"])

# Define an entity for the order_id. You can think of an entity as a primary key used to
# fetch features.
order = Entity(name="order", join_keys=["ORDER_ID"])

# Define an entity for the seller_id. You can think of an entity as a primary key used to
# fetch features.
seller = Entity(name="seller", join_keys=["SELLER_ID"])

# Define an entity for the product_id. You can think of an entity as a primary key used to
# fetch features.
product = Entity(name="product", join_keys=["PRODUCT_ID"])

# Define an entity for the zip_code_prefix. You can think of an entity as a primary key used to
# fetch features.
seller_zip_code_prefix = Entity(name="seller_zip_code_prefix", join_keys=["SELLER_ZIP_CODE_PREFIX"])

# Define an entity for the zip_code_prefix. You can think of an entity as a primary key used to
# fetch features.
geolocation_zip_code_prefix = Entity(name="geolocation_zip_code_prefix", join_keys=["GEOLOCATION_ZIP_CODE_PREFIX"])

# Define an entity for the zip_code_prefix. You can think of an entity as a primary key used to
# fetch features.
customer_zip_code_prefix = Entity(name="customer_zip_code_prefix", join_keys=["CUSTOMER_ZIP_CODE_PREFIX"])

# Defines a data source from which feature values can be retrieved. Sources are queried when building training
# datasets or materializing features into an online store.
project_name = yaml.safe_load(open("feature_store.yaml"))["project"]

# OLIST_CUSTOMERS data source
olist_customers_source = SnowflakeSource(
    database=yaml.safe_load(open("feature_store.yaml"))["offline_store"]["database"],
    schema=yaml.safe_load(open("feature_store.yaml"))["offline_store"]["schema"],
    timestamp_field="EVENT_TIMESTAMP",
    created_timestamp_column="CREATED_TIMESTAMP",
    table="OLIST_CUSTOMERS"
)

olist_customers_fv = FeatureView(
    name="olist_customers_fv",
    entities=[customer, customer_zip_code_prefix],
    ttl=timedelta(weeks=52 * 10),
    schema=[
        Field(name="CUSTOMER_ID", dtype=String),
        Field(name="CUSTOMER_UNIQUE_ID", dtype=String),
        Field(name="CUSTOMER_ZIP_CODE_PREFIX", dtype=Int64),
        Field(name="CUSTOMER_CITY", dtype=String),
        Field(name="CUSTOMER_STATE", dtype=String),
    ],
    source=olist_customers_source,
    tags={"team": "customers"},
)

# OLIST_GEOLOCATION data source
geolocation_stats_source = SnowflakeSource(
    database=yaml.safe_load(open("feature_store.yaml"))["offline_store"]["database"],
    schema=yaml.safe_load(open("feature_store.yaml"))["offline_store"]["schema"],
    timestamp_field="EVENT_TIMESTAMP",
    created_timestamp_column="CREATED_TIMESTAMP",
    table="OLIST_GEOLOCATION"
)

geolocation_fv = FeatureView(
    name="geolocation_fv",
    entities=[geolocation_zip_code_prefix],
    ttl=timedelta(weeks=52 * 10),
    schema=[
        Field(name="GEOLOCATION_ZIP_CODE_PREFIX", dtype=Int64),
        Field(name="GEOLOCATION_LAT", dtype=Float64),
        Field(name="GEOLOCATION_LNG", dtype=Float64),
        Field(name="GEOLOCATION_CITY", dtype=String),
        Field(name="GEOLOCATION_STATE", dtype=String),
    ],
    source=geolocation_stats_source,
    tags={"team": "geolocation"},
)

# OLIST_ORDER_ITEMS data source
order_items_stats_source = SnowflakeSource(
    database=yaml.safe_load(open("feature_store.yaml"))["offline_store"]["database"],
    schema=yaml.safe_load(open("feature_store.yaml"))["offline_store"]["schema"],
    timestamp_field="EVENT_TIMESTAMP",
    created_timestamp_column="CREATED_TIMESTAMP",
    table="OLIST_ORDER_ITEMS"
)

order_items_fv = FeatureView(
    name="order_items_fv",
    #    entities=[product, seller, order],
    entities=[order],
    ttl=timedelta(weeks=52 * 10),
    schema=[
        Field(name="ORDER_ID", dtype=String),
        Field(name="ORDER_ITEM_ID", dtype=Int64),
        Field(name="PRODUCT_ID", dtype=String),
        Field(name="SELLER_ID", dtype=String),
        Field(name="SHIPPING_LIMIT_DATE", dtype=UnixTimestamp),

        Field(name="PRICE", dtype=Float64),
        Field(name="FREIGHT_VALUE", dtype=Float64),
    ],
    source=order_items_stats_source,
    tags={"team": "order_items"},
)

# OLIST_ORDER_PAYMENTS data source
order_payments_stats_source = SnowflakeSource(
    database=yaml.safe_load(open("feature_store.yaml"))["offline_store"]["database"],
    schema=yaml.safe_load(open("feature_store.yaml"))["offline_store"]["schema"],
    timestamp_field="EVENT_TIMESTAMP",
    created_timestamp_column="CREATED_TIMESTAMP",
    table="OLIST_ORDER_PAYMENTS"
)

order_payments_fv = FeatureView(
    name="order_payments_fv",
    entities=[order],
    ttl=timedelta(weeks=52 * 10),
    schema=[
        Field(name="ORDER_ID", dtype=String),
        Field(name="PAYMENT_SEQUENTIAL", dtype=Int64),
        Field(name="PAYMENT_TYPE", dtype=String),
        Field(name="PAYMENT_INSTALLMENTS", dtype=Int64),
        Field(name="PAYMENT_VALUE", dtype=Float64),

    ],
    source=order_payments_stats_source,
    tags={"team": "payments"},
)

# OLIST_ORDER_REVIEWS data source
order_reviews_stats_source = SnowflakeSource(
    database=yaml.safe_load(open("feature_store.yaml"))["offline_store"]["database"],
    schema=yaml.safe_load(open("feature_store.yaml"))["offline_store"]["schema"],
    timestamp_field="EVENT_TIMESTAMP",
    created_timestamp_column="CREATED_TIMESTAMP",
    table="OLIST_ORDER_REVIEWS"
)

order_reviews_fv = FeatureView(
    name="order_reviews_fv",
    entities=[order],
    ttl=timedelta(weeks=52 * 10),
    schema=[
        Field(name="REVIEW_ID", dtype=String),
        Field(name="ORDER_ID", dtype=String),
        Field(name="REVIEW_SCORE", dtype=Int64),
        Field(name="REVIEW_COMMENT_TITLE", dtype=String),
        Field(name="REVIEW_COMMENT_MESSAGE", dtype=String),
        Field(name="REVIEW_CREATION_DATE", dtype=UnixTimestamp),
        Field(name="REVIEW_ANSWER_TIMESTAMP", dtype=UnixTimestamp),

    ],
    source=order_reviews_stats_source,
    tags={"team": "reviews"},
)

# OLIST_ORDERS data source
orders_stats_source = SnowflakeSource(
    database=yaml.safe_load(open("feature_store.yaml"))["offline_store"]["database"],
    schema=yaml.safe_load(open("feature_store.yaml"))["offline_store"]["schema"],
    timestamp_field="EVENT_TIMESTAMP",
    created_timestamp_column="CREATED_TIMESTAMP",
    table="OLIST_ORDERS"
)

orders_fv = FeatureView(
    name="orders_fv",
    entities=[order, customer],
    ttl=timedelta(weeks=52 * 10),
    schema=[
        Field(name="ORDER_ID", dtype=String),
        Field(name="CUSTOMER_ID", dtype=String),
        Field(name="ORDER_STATUS", dtype=String),
        Field(name="ORDER_PURCHASE_TIMESTAMP", dtype=UnixTimestamp),
        Field(name="ORDER_APPROVED_AT", dtype=UnixTimestamp),
        Field(name="ORDER_DELIVERED_CARRIER_DATE", dtype=UnixTimestamp),
        Field(name="ORDER_DELIVERED_CUSTOMER_DATE", dtype=UnixTimestamp),
        Field(name="ORDER_ESTIMATED_DELIVERY_DATE", dtype=UnixTimestamp),

    ],
    source=orders_stats_source,
    tags={"team": "orders"},
)

# OLIST_PRODUCTS data source
products_stats_source = SnowflakeSource(
    database=yaml.safe_load(open("feature_store.yaml"))["offline_store"]["database"],
    schema=yaml.safe_load(open("feature_store.yaml"))["offline_store"]["schema"],
    timestamp_field="EVENT_TIMESTAMP",
    created_timestamp_column="CREATED_TIMESTAMP",
    table="OLIST_PRODUCTS"
)

products_fv = FeatureView(
    name="products_fv",
    entities=[product],
    ttl=timedelta(weeks=52 * 10),
    schema=[
        Field(name="PRODUCT_ID", dtype=String),
        Field(name="PRODUCT_CATEGORY_NAME", dtype=String),
        Field(name="PRODUCT_NAME_LENGHT", dtype=Float64),
        Field(name="PRODUCT_DESCRIPTION_LENGHT", dtype=Float64),
        Field(name="PRODUCT_PHOTOS_QTY", dtype=Float64),
        Field(name="PRODUCT_WEIGHT_G", dtype=Float64),
        Field(name="PRODUCT_LENGTH_CM", dtype=Float64),
        Field(name="PRODUCT_HEIGHT_CM", dtype=Float64),
        Field(name="PRODUCT_WIDTH_CM", dtype=Float64),
    ],
    source=products_stats_source,
    tags={"team": "products"},
)

# OLIST_SELLERS data source
sellers_stats_source = SnowflakeSource(
    database=yaml.safe_load(open("feature_store.yaml"))["offline_store"]["database"],
    schema=yaml.safe_load(open("feature_store.yaml"))["offline_store"]["schema"],
    timestamp_field="EVENT_TIMESTAMP",
    created_timestamp_column="CREATED_TIMESTAMP",
    table="OLIST_SELLERS"
)

# PRODUCT_CATEGORY_NAMES_TRANSLATION
product_category_stats_source = SnowflakeSource(
    database=yaml.safe_load(open("feature_store.yaml"))["offline_store"]["database"],
    schema=yaml.safe_load(open("feature_store.yaml"))["offline_store"]["schema"],
    timestamp_field="EVENT_TIMESTAMP",
    created_timestamp_column="CREATED_TIMESTAMP",
    table="PRODUCT_CATEGORY_NAMES_TRANSLATION"
)


@on_demand_feature_view(
    sources=[order_items_fv],
    schema=[
        Field(name="PRICE_TO_INR", dtype=Float64),
    ],
)
def transformed_dollar_to_inr(inputs: pd.DataFrame) -> pd.DataFrame:
    df = pd.DataFrame()
    df["PRICE_TO_INR"] = inputs["PRICE"] * 80
    return df


@on_demand_feature_view(
    sources=[orders_fv],
    schema=[
        Field(name="TIME_TAKEN_TO_APPROVE(IN_MNTS)", dtype=Float64),
    ],
)
def time_taken_to_approve(inputs: pd.DataFrame) -> pd.DataFrame:
    df = pd.DataFrame()
    df["TIME_TAKEN_TO_APPROVE(IN_MNTS)"] = (inputs["ORDER_APPROVED_AT"] - inputs[
        "ORDER_PURCHASE_TIMESTAMP"]) / np.timedelta64(1, 'm')
    return df


customer_orders_fs = FeatureService(
    name="customer_orders_fs",
    features=[olist_customers_fv, order_items_fv, order_payments_fv, orders_fv, transformed_dollar_to_inr,
              time_taken_to_approve]
)


