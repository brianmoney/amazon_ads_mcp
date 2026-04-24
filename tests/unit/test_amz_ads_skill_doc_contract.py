from pathlib import Path


def test_amz_ads_skill_documents_supported_sd_surface_and_boundaries():
    skill_path = (
        Path(__file__).resolve().parents[2] / ".opencode/skills/amz-ads/SKILL.md"
    )
    content = skill_path.read_text(encoding="utf-8")

    assert "`list_sd_campaigns`" in content
    assert "`get_sd_performance`" in content
    assert "`sd_report_status`" in content

    assert "preserve the returned `report_id`" in content
    assert "poll with `sd_report_status`" in content
    assert "`get_sd_performance(resume_from_report_id=...)`" in content

    assert "Sponsored Display writes" in content
    assert "audience mutations" in content
    assert "creative automation" in content
    assert "all Sponsored Brands workflows" in content
