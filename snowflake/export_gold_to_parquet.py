"""Exports ClaimSense Gold tables to Parquet files for Snowflake staging."""

from pathlib import Path

import pandas as pd

from claimsense.db.client_factory import get_db_client


def export_gold_tables_to_parquet(output_dir: Path | None = None) -> dict[str, int]:
    out_dir = output_dir or (Path(__file__).parent / "staged_data")
    out_dir.mkdir(parents=True, exist_ok=True)

    db = get_db_client()
    tables = [
        "dim_customer",
        "dim_policy",
        "dim_claim_type",
        "dim_date",
        "fact_claims",
        "quarantine_claims",
    ]

    counts = {}
    print(f"Exporting Gold & Silver tables to Parquet at {out_dir}...")

    for tbl in tables:
        rows = db.execute_query(f"SELECT * FROM {tbl}")
        if rows:
            df = pd.DataFrame(rows)
            parquet_path = out_dir / f"{tbl}.parquet"
            df.to_parquet(parquet_path, index=False)
            counts[tbl] = len(df)
            print(f" - Exported {tbl}: {len(df)} rows -> {parquet_path.name}")
        else:
            counts[tbl] = 0

    return counts


if __name__ == "__main__":
    export_gold_tables_to_parquet()
