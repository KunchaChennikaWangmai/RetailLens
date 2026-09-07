"""
Retail Lens — BigQuery Client

Thin abstraction layer for accessing the retail_lens_patchamomma dataset.
SQL queries and analytical tools will be layered on top in future phases.

Existing tables (do NOT recreate or modify):
  - inventory_metadata
  - sales_transactions
  - customer_bills
  - workforce_shifts
"""

import os
from typing import Optional

from google.cloud import bigquery


DATASET_ID = "retail_lens_patchamomma"


def get_client(project: Optional[str] = None) -> bigquery.Client:
    """Return an authenticated BigQuery client.

    Args:
        project: GCP project ID.  Falls back to GOOGLE_CLOUD_PROJECT env var.

    Returns:
        A google.cloud.bigquery.Client instance.
    """
    project = project or os.getenv("GOOGLE_CLOUD_PROJECT")
    return bigquery.Client(project=project)


def get_dataset_ref(client: bigquery.Client) -> bigquery.DatasetReference:
    """Return a DatasetReference to the retail_lens_patchamomma dataset."""
    return client.dataset(DATASET_ID)
