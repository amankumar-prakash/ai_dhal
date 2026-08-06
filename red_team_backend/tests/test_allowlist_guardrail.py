from app.guardrails import demo_blocks_profile, in_allowlist


def test_allowlist_blocks_out_of_scope():
    assert in_allowlist("evil.example", "corp.internal") is False
    assert in_allowlist("edge.corp.internal", "corp.internal") is True


def test_empty_allowlist_permits():
    assert in_allowlist("anything", "") is True


def test_demo_safe_blocks_exploit():
    assert demo_blocks_profile("exploit-pack", "1") is True
    assert demo_blocks_profile("surface-recon", "1") is False
