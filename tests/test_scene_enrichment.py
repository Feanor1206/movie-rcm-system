from ai.enrich.keyframes import is_duplicate
from ai.enrich.scenes import group_shots


def test_keyframe_hash_dedup_uses_hamming_distance():
    anchor = 0x1111111111111111
    assert is_duplicate(anchor, [anchor])
    assert is_duplicate(anchor ^ 0b1111, [anchor])
    assert not is_duplicate(anchor ^ 0b11111, [anchor])


def test_scene_boundary_prefers_visual_transition_and_dialogue_pause():
    cuts = [48_000, 60_000, 70_000, 120_000]
    cues = [{"start_ms": 58_000, "end_ms": 64_000}, {"start_ms": 92_000, "end_ms": 96_000}]
    samples = [(47_000, 0), (48_000, 0), (59_000, 0), (60_000, 0),
               (69_000, 0), (70_000, (1 << 63) - 1)]
    grouped = group_shots(145_000, cuts, cues, samples)
    assert grouped == [(0, 70_000), (70_000, 145_000)]


def test_scenes_cover_timeline_even_when_a_video_has_no_detected_cuts():
    grouped = group_shots(192_000, [], [], [])
    assert grouped[0][0] == 0
    assert grouped[-1][1] == 192_000
    assert all(30_000 <= end - start <= 90_000 for start, end in grouped)
    assert all(left[1] == right[0] for left, right in zip(grouped, grouped[1:]))
