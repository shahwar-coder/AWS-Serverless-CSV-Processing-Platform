"""Validate and summarize the first CSV report format."""

import csv
import io
from decimal import Decimal, InvalidOperation


class CsvValidationError(ValueError):
    pass


MAX_CSV_BYTES = 5 * 1024 * 1024
MAX_UNIQUE_PRODUCTS = 1000
REQUIRED_COLUMNS = ("product", "quantity", "price")


def summarize_csv(payload: bytes) -> dict:
    if len(payload) > MAX_CSV_BYTES:
        raise CsvValidationError("CSV exceeds the 5 MiB size limit.")
    try:
        source = io.StringIO(payload.decode("utf-8-sig"), newline="")
    except UnicodeDecodeError as error:
        raise CsvValidationError("CSV must be UTF-8.") from error
    reader = csv.DictReader(source, strict=True)
    try:
        fieldnames = reader.fieldnames
    except csv.Error as error:
        raise CsvValidationError("Malformed CSV.") from error
    if not fieldnames or any(fieldnames.count(name) != 1 for name in REQUIRED_COLUMNS):
        raise CsvValidationError("CSV must contain product,quantity,price headers.")
    row_count = 0
    total_quantity = 0
    total_revenue = Decimal("0")
    products = {}
    try:
        for row in reader:
            product = row.get("product")
            if not product or not product.strip() or None in row:
                raise CsvValidationError(f"Invalid product on row {row_count + 1}.")
            try:
                quantity = int(row["quantity"])
                price = Decimal(row["price"])
            except (TypeError, ValueError, InvalidOperation):
                raise CsvValidationError(f"Invalid number on row {row_count + 1}.") from None
            if quantity < 0 or not price.is_finite() or price < 0:
                raise CsvValidationError(f"Negative or non-finite value on row {row_count + 1}.")

            name = product.strip()
            product_key = name.casefold()
            if product_key not in products:
                if len(products) >= MAX_UNIQUE_PRODUCTS:
                    raise CsvValidationError("CSV exceeds the 1,000-product limit.")
                products[product_key] = {"product": name, "quantity": 0, "revenue": Decimal("0")}
            row_count += 1
            total_quantity += quantity
            revenue = quantity * price
            total_revenue += revenue
            products[product_key]["quantity"] += quantity
            products[product_key]["revenue"] += revenue
    except csv.Error as error:
        raise CsvValidationError("Malformed CSV.") from error
    breakdown = sorted(
        products.values(),
        key=lambda item: (-item["revenue"], item["product"].casefold(), item["product"]),
    )
    return {
        "currency": "INR",
        "row_count": row_count,
        "total_quantity": total_quantity,
        "total_revenue": str(total_revenue),
        "unique_products": len(breakdown),
        "products": [
            {"product": item["product"], "quantity": item["quantity"], "revenue": str(item["revenue"])}
            for item in breakdown
        ],
    }
