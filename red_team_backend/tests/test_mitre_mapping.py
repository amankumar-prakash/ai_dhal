"""MITRE mapping helpers exercised via CAI stub stages.

CAI DISABLED — tests commented out.
"""
# from app.adapters import cai_client
# from app.settings import WorkerSettings
# import pytest
#
#
# @pytest.mark.asyncio
# async def test_mitre_mapping_stages():
#     plan = await cai_client.plan_chain({"job_id": "1", "profile": "deep"}, WorkerSettings(llm_stub="1"))
#     assert "recon" in plan["stages"]
#     assert "exfiltration" in plan["stages"]
