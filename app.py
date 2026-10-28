
from flask import Flask, render_template, request, jsonify, Response
import pandas as pd
from pathlib import Path
from io import StringIO

app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "sales.csv"

COLUMNS = [
    "order_date", "product", "category",
    "region", "quantity", "unit_price"
]


def create_sample_data():
    products = [
        ("Laptop", "Electronics", 40000),
        ("Mouse", "Accessories", 500),
        ("Keyboard", "Accessories", 1200),
        ("Monitor", "Electronics", 10000),
        ("Headphones", "Accessories", 1800),
        ("Webcam", "Accessories", 2500)
    ]

    rows = []
    for i in range(120):
        product, category, price = products[i % len(products)]
        date = pd.Timestamp("2026-01-01") + pd.Timedelta(days=i * 2)

        rows.append({
            "order_date": date.strftime("%Y-%m-%d"),
            "product": product,
            "category": category,
            "region": ["North", "South", "East", "West"][i % 4],
            "quantity": i % 5 + 1,
            "unit_price": price
        })

    pd.DataFrame(rows).to_csv(DATA_FILE, index=False)


def load_data():
    if not DATA_FILE.exists() or DATA_FILE.stat().st_size == 0:
        create_sample_data()

    df = pd.read_csv(DATA_FILE)

    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            "CSV mein required columns missing hain: "
            + ", ".join(missing)
        )

    df["order_date"] = pd.to_datetime(
        df["order_date"], errors="coerce"
    )
    df["quantity"] = pd.to_numeric(
        df["quantity"], errors="coerce"
    )
    df["unit_price"] = pd.to_numeric(
        df["unit_price"], errors="coerce"
    )

    df = df.dropna(subset=COLUMNS).copy()
    df = df[
        (df["quantity"] >= 0) &
        (df["unit_price"] >= 0)
    ].copy()

    for col in ["product", "category", "region"]:
        df[col] = df[col].astype(str)

    df["revenue"] = df["quantity"] * df["unit_price"]
    return df


def apply_filters(df):
    category = request.args.get("category", "")
    region = request.args.get("region", "")
    search = request.args.get("search", "").strip().lower()

    if category:
        df = df[df["category"] == category]

    if region:
        df = df[df["region"] == region]

    if search:
        mask = (
            df["product"].str.lower().str.contains(search, regex=False)
            | df["category"].str.lower().str.contains(search, regex=False)
            | df["region"].str.lower().str.contains(search, regex=False)
        )
        df = df[mask]

    return df.copy()


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/data")
def api_data():
    try:
        original = load_data()
        df = apply_filters(original)

        monthly = (
            df.assign(month=df["order_date"].dt.strftime("%Y-%m"))
            .groupby("month")["revenue"]
            .sum()
            .sort_index()
        )

        products = (
            df.groupby("product")["revenue"]
            .sum()
            .sort_values(ascending=False)
            .head(8)
        )

        categories = (
            df.groupby("category")["revenue"]
            .sum()
            .sort_values(ascending=False)
        )

        records = df.sort_values(
            "order_date", ascending=False
        ).head(200).copy()

        records["order_date"] = records[
            "order_date"
        ].dt.strftime("%Y-%m-%d")

        total_revenue = float(df["revenue"].sum())
        total_orders = len(df)

        return jsonify({
            "stats": {
                "revenue": total_revenue,
                "orders": total_orders,
                "units": float(df["quantity"].sum()),
                "average": (
                    total_revenue / total_orders
                    if total_orders else 0
                )
            },
            "monthly": {
                "labels": monthly.index.tolist(),
                "values": monthly.tolist()
            },
            "products": {
                "labels": products.index.tolist(),
                "values": products.tolist()
            },
            "categories": {
                "labels": categories.index.tolist(),
                "values": categories.tolist()
            },
            "records": records[
                COLUMNS + ["revenue"]
            ].to_dict(orient="records"),
            "filters": {
                "categories": sorted(original["category"].unique().tolist()),
                "regions": sorted(original["region"].unique().tolist())
            }
        })

    except (ValueError, KeyError, pd.errors.ParserError) as error:
        return jsonify({"error": str(error)}), 400


@app.route("/api/upload", methods=["POST"])
def upload_csv():
    file = request.files.get("file")

    if not file or not file.filename.lower().endswith(".csv"):
        return jsonify({
            "error": "Please select a CSV file."
        }), 400

    try:
        content = file.read().decode("utf-8-sig")
        df = pd.read_csv(StringIO(content))

        if not set(COLUMNS).issubset(df.columns):
            return jsonify({
                "error": "CSV columns must be: " + ", ".join(COLUMNS)
            }), 400

        df["order_date"] = pd.to_datetime(
            df["order_date"], errors="coerce"
        )
        df["quantity"] = pd.to_numeric(
            df["quantity"], errors="coerce"
        )
        df["unit_price"] = pd.to_numeric(
            df["unit_price"], errors="coerce"
        )

        df = df.dropna(subset=COLUMNS).copy()
        df = df[
            (df["quantity"] >= 0) &
            (df["unit_price"] >= 0)
        ].copy()

        if df.empty:
            return jsonify({"error": "No valid rows found."}), 400

        df["order_date"] = df[
            "order_date"
        ].dt.strftime("%Y-%m-%d")

        df.to_csv(DATA_FILE, index=False)

        return jsonify({
            "message": f"Upload successful! {len(df)} rows loaded."
        })

    except (UnicodeDecodeError, ValueError, pd.errors.ParserError) as error:
        return jsonify({"error": f"Invalid CSV: {error}"}), 400


@app.route("/api/export")
def export_csv():
    try:
        df = apply_filters(load_data())
        df["order_date"] = df["order_date"].dt.strftime("%Y-%m-%d")

        return Response(
            df.to_csv(index=False),
            mimetype="text/csv",
            headers={
                "Content-Disposition":
                "attachment; filename=sales_report.csv"
            }
        )

    except (ValueError, KeyError, pd.errors.ParserError) as error:
        return jsonify({"error": str(error)}), 400


if __name__ == "__main__":
    app.run(debug=True)

