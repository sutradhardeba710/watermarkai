"""Admin Panel Phase 6 pure-logic tests — models, presets, feature flags,
notifications, maintenance (PRD §19, §20, §23, §26.5, §26.6).

No DB / SQLAlchemy — runs on the 32-bit dev box.
"""
from __future__ import annotations

import pytest

from app.core.errors import AppError
from app.services import admin_service as svc


# ---------------------------------------------------------------------------
# validate_model_type / validate_model_action (PRD §19.1, §19.4)
# ---------------------------------------------------------------------------


def test_validate_model_type_normalises_and_accepts_known():
    assert svc.validate_model_type("  Watermark_Detection ") == "watermark_detection"


def test_validate_model_type_rejects_unknown():
    with pytest.raises(AppError) as exc:
        svc.validate_model_type("magic")
    assert exc.value.status_code == 422


def test_validate_model_action_rejects_unknown():
    with pytest.raises(AppError):
        svc.validate_model_action("explode")


# ---------------------------------------------------------------------------
# model_action_effects (PRD §19.4)
# ---------------------------------------------------------------------------


def test_enable_production_activates():
    eff = svc.model_action_effects("enable_production")
    assert eff["status"] == "active"
    assert eff["set_default"] is None
    assert eff["requires_reason"] is False


def test_enable_testing_moves_to_testing():
    assert svc.model_action_effects("enable_testing")["status"] == "testing"


def test_set_default_is_flag_only():
    eff = svc.model_action_effects("set_default")
    assert eff["status"] is None
    assert eff["set_default"] is True
    assert eff["set_fallback"] is None


def test_set_fallback_is_flag_only():
    eff = svc.model_action_effects("set_fallback")
    assert eff["status"] is None
    assert eff["set_fallback"] is True


def test_rollback_requires_reason_and_marks_candidate():
    eff = svc.model_action_effects("rollback")
    assert eff["status"] == "rollback_candidate"
    assert eff["requires_reason"] is True


def test_disable_and_deprecate_require_reason():
    assert svc.model_action_effects("disable")["requires_reason"] is True
    assert svc.model_action_effects("deprecate")["requires_reason"] is True
    assert svc.model_action_effects("deprecate")["status"] == "deprecated"


# ---------------------------------------------------------------------------
# validate_rollout (PRD §19.5)
# ---------------------------------------------------------------------------


def test_rollout_percentage_within_bounds():
    assert svc.validate_rollout("percentage", 40) == ("percentage", 40)


def test_rollout_percentage_out_of_bounds_rejected():
    with pytest.raises(AppError):
        svc.validate_rollout("percentage", 150)


def test_rollout_non_percentage_zeroes_pct():
    assert svc.validate_rollout("internal", 55) == ("internal", 0)
    assert svc.validate_rollout("full", None) == ("full", 0)


def test_rollout_unknown_strategy_rejected():
    with pytest.raises(AppError):
        svc.validate_rollout("carrier_pigeon", 0)


# ---------------------------------------------------------------------------
# validate_preset_fields (PRD §20.2)
# ---------------------------------------------------------------------------


def test_preset_requires_name():
    with pytest.raises(AppError):
        svc.validate_preset_fields(name="  ")


def test_preset_rejects_bad_sampling_rate():
    with pytest.raises(AppError):
        svc.validate_preset_fields(name="Fast", frame_sampling_rate=0)


def test_preset_rejects_negative_expansion():
    with pytest.raises(AppError):
        svc.validate_preset_fields(name="Fast", mask_expansion=-1)


def test_preset_rejects_out_of_range_quality():
    with pytest.raises(AppError):
        svc.validate_preset_fields(name="HQ", encoding_quality=101)


def test_preset_accepts_valid():
    # Should not raise.
    svc.validate_preset_fields(
        name="Balanced", frame_sampling_rate=2, mask_expansion=4,
        feathering=6, encoding_quality=80, expected_credit_cost=10,
    )


# ---------------------------------------------------------------------------
# merge_feature_flags (PRD §26.5)
# ---------------------------------------------------------------------------


def test_merge_flags_fills_catalogue_defaults():
    merged = svc.merge_feature_flags([])
    keys = {f["key"] for f in merged}
    assert set(svc.FEATURE_FLAG_KEYS).issubset(keys)
    # Every catalogue flag defaults to enabled with a derived label.
    promo = next(f for f in merged if f["key"] == "promo_codes")
    assert promo["enabled"] is True
    assert promo["label"] == "Promo Codes"


def test_merge_flags_stored_row_wins():
    merged = svc.merge_feature_flags([{"key": "promo_codes", "enabled": False, "label": "Promos"}])
    promo = next(f for f in merged if f["key"] == "promo_codes")
    assert promo["enabled"] is False
    assert promo["label"] == "Promos"


def test_merge_flags_preserves_catalogue_order():
    merged = svc.merge_feature_flags([])
    ordered = [f["key"] for f in merged[: len(svc.FEATURE_FLAG_KEYS)]]
    assert ordered == list(svc.FEATURE_FLAG_KEYS)


def test_merge_flags_appends_unknown_stored_keys():
    merged = svc.merge_feature_flags([{"key": "legacy_thing", "enabled": True}])
    assert any(f["key"] == "legacy_thing" for f in merged)


# ---------------------------------------------------------------------------
# normalise_maintenance (PRD §26.6)
# ---------------------------------------------------------------------------


def test_maintenance_defaults_all_present():
    state = svc.normalise_maintenance(None)
    for key in svc.MAINTENANCE_DEFAULTS:
        assert key in state
    assert state["maintenance_enabled"] is False
    assert state["allow_administrators"] is True


def test_maintenance_overlays_stored_values():
    state = svc.normalise_maintenance({"maintenance_enabled": True, "public_message": "Back at 5pm"})
    assert state["maintenance_enabled"] is True
    assert state["public_message"] == "Back at 5pm"
    # Untouched fields keep their defaults.
    assert state["pause_new_uploads"] is True


def test_maintenance_ignores_none_values():
    state = svc.normalise_maintenance({"public_message": None})
    assert state["public_message"] == ""


# ---------------------------------------------------------------------------
# validate_broadcast (PRD §23.3)
# ---------------------------------------------------------------------------


def test_broadcast_valid_kind_and_target():
    assert svc.validate_broadcast("feature", "free_users") == ("feature", "free_users")


def test_broadcast_defaults_target_all():
    assert svc.validate_broadcast("in_app", "")[1] == "all"


def test_broadcast_rejects_bad_kind():
    with pytest.raises(AppError):
        svc.validate_broadcast("spam", "all")


def test_broadcast_rejects_bad_target():
    with pytest.raises(AppError):
        svc.validate_broadcast("in_app", "everyone_everywhere")


# ---------------------------------------------------------------------------
# render_template_preview (PRD §23.1)
# ---------------------------------------------------------------------------


def test_template_preview_substitutes_variables():
    tmpl = {
        "subject": "Hi {{name}}",
        "html_content": "<p>Your job {{job_id}} is done</p>",
        "text_content": "Job {{job_id}} done",
    }
    out = svc.render_template_preview(tmpl, {"name": "Ada", "job_id": "abc123"})
    assert out["subject"] == "Hi Ada"
    assert "abc123" in out["html_content"]
    assert out["text_content"] == "Job abc123 done"


def test_template_preview_leaves_unknown_placeholders():
    out = svc.render_template_preview({"subject": "Hi {{name}}", "html_content": "", "text_content": ""}, {})
    assert out["subject"] == "Hi {{name}}"


def test_template_preview_handles_missing_fields():
    out = svc.render_template_preview({}, {"x": "y"})
    assert out == {"subject": "", "html_content": "", "text_content": ""}
