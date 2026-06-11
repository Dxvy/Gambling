"""
Supabase admin client — uses the service-role key to bypass Row Level Security.

Only used by trusted backend jobs (e.g. the prediction results resolver) that
need to read/write rows across all users.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

_SUPABASE_URL = os.getenv("SUPABASE_URL", "")
_SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

_admin_client: Client | None = None
if _SUPABASE_URL and _SUPABASE_SERVICE_KEY:
    _admin_client = create_client(_SUPABASE_URL, _SUPABASE_SERVICE_KEY)


def get_admin_client() -> Client | None:
    """Return the service-role Supabase client, or None if not configured."""
    return _admin_client
