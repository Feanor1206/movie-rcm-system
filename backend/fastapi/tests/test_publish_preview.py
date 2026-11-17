import copy

import pytest

from ai.enrich.common import CATALOG, read
from ai.enrich.publish_preview import approve, review_template, scope_catalog, validate


EPISODE = "ep_jadoo_s01_0022"
ASSET = "asset_jadoo_s01_v0022"
STAMP = "2026-11-10T00:00:00+00:00"


def draft_catalog():
    original = read(CATALOG)
    base = scope_catalog(original, [EPISODE])
    draft = copy.deepcopy(base)
    asset = next(row for row in base["media_assets"] if row["id"] == ASSET)
    provenance = {**asset["record"]["provenance"], "origin": "machine_generated", "verification": "unverified",
                  "tool_or_model": "Test ASR", "tool_revision": "1", "annotated_at": STAMP}
    draft["text_tracks"] = [{"id": f"{EPISODE}.track.asr.vi", "media_asset_id": ASSET,
        "kind": "transcript", "language": "vi", "format": "inline", "external_file": None,
        "cues": [{"id": f"{EPISODE}.cue.00001", "start_ms": 0, "end_ms": 1000,
                  "text": "Dữ liệu kiểm thử", "speaker_character_ids": [], "confidence": None}],
        "provenance": provenance, "record": {"status": "draft", "revision": 1, "created_at": STAMP,
                                             "updated_at": STAMP, "provenance": provenance}}]
    validate(draft)
    return base, draft


def test_reviewed_publish_requires_exact_record_approval_and_keeps_model_provenance():
    base, draft = draft_catalog()
    review = review_template(base, draft)
    assert review["records"][0]["approved"] is False
    review["reviewer"] = "Reviewer for test fixture"
    with pytest.raises(ValueError, match="Missing approval"):
        approve(base, draft, review, STAMP)
    review["records"][0]["approved"] = True
    accepted = approve(base, draft, review, STAMP)
    track = accepted["text_tracks"][0]
    assert [row["id"] for row in accepted["episodes"]] == [EPISODE]
    assert track["record"]["status"] == "ready"
    assert track["provenance"]["verification"] == "human_verified"
    assert track["provenance"]["origin"] == "machine_generated"
    assert track["provenance"]["tool_or_model"] == "Test ASR"
    assert draft["text_tracks"][0]["record"]["status"] == "draft"
    draft["text_tracks"][0]["cues"][0]["text"] += " changed"
    with pytest.raises(ValueError, match="changed content"):
        approve(base, draft, review, STAMP)


def test_review_scope_rejects_an_unrelated_generated_record():
    base, draft = draft_catalog()
    review = review_template(base, draft)
    review["reviewer"] = "Reviewer for test fixture"
    review["records"].append({"id": "unrelated-record", "approved": True, "sha256": "0" * 64})
    with pytest.raises(ValueError, match="exactly the generated"):
        approve(base, draft, review, STAMP)
