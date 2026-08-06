"""RLS write denial is enforced by migration; memory mode documents expectation."""


def test_rls_policy_documented():
    # Migration 20260804120000 revokes INSERT/UPDATE/DELETE from authenticated.
    from pathlib import Path

    sql = Path(__file__).resolve().parents[2] / "secure_dash/supabase/migrations/20260804120000_red_blue_platform.sql"
    text = sql.read_text()
    assert "REVOKE INSERT, UPDATE, DELETE ON public.assets FROM authenticated" in text
    assert "REVOKE INSERT, UPDATE, DELETE ON public.findings FROM authenticated" in text
