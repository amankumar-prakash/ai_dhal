import pytest

from app.pipelines import patch


@pytest.mark.asyncio
async def test_patch_dry_run():
    out = await patch.dry_run("upgrade-package")
    assert out["applied"] is False
    assert out["playbook"] == "upgrade-package"
