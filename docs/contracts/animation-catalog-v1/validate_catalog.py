"""Validate catalog structure and internal consistency; never import or open media."""
import json
import sys
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parent
COLLECTIONS = ('genres', 'attribute_scales', 'sources', 'series', 'seasons',
               'episodes', 'segments', 'characters', 'media_assets', 'text_tracks', 'scenes')
REFERENCES = {
    'source_ids': 'sources', 'source_id': 'sources', 'genre_ids': 'genres',
    'scale_id': 'attribute_scales', 'series_id': 'series', 'series_ids': 'series',
    'season_id': 'seasons', 'episode_id': 'episodes', 'segment_id': 'segments',
    'character_id': 'characters', 'character_ids': 'characters',
    'speaker_character_ids': 'characters', 'media_asset_id': 'media_assets',
    'related_asset_id': 'media_assets', 'transcript_cue_ids': 'cues',
}


def validate(data):
    schema = json.loads((ROOT / 'dippie.catalog.v1.schema.json').read_text(encoding='utf-8'))
    Draft202012Validator.check_schema(schema)
    errors = [f"/{'/'.join(map(str, e.absolute_path))}: {e.message}"
              for e in Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(data)]
    if errors:
        return errors
    tables = {name: {row['id']: row for row in data[name]} for name in COLLECTIONS}
    tables['cues'] = {cue['id']: cue for track in data['text_tracks'] for cue in track['cues']}
    cue_asset = {cue['id']: track['media_asset_id'] for track in data['text_tracks'] for cue in track['cues']}
    seen = set()

    def check_id(value, location):
        if value in seen:
            errors.append(f'{location}: duplicate global id {value}')
        seen.add(value)

    def walk(value, path=''):
        if isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f'{path}/{index}')
        elif isinstance(value, dict):
            if 'id' in value:
                check_id(value['id'], path + '/id')
            for key, child in value.items():
                if key in REFERENCES and child is not None:
                    for target in child if isinstance(child, list) else [child]:
                        if target not in tables[REFERENCES[key]]:
                            errors.append(f'{path}/{key}: missing {REFERENCES[key]} id {target}')
                walk(child, path + '/' + key)
            if 'translations' in value:
                langs = [item['language'] for item in value['translations']]
                if len(langs) != len(set(langs)):
                    errors.append(path + '/translations: duplicate language')
                for item in value['translations']:
                    if item['title'] is None and item['synopsis'] is None:
                        errors.append(path + '/translations: title and synopsis cannot both be null')
            if 'ratings' in value:
                for rating in value['ratings']:
                    if rating['value'] > rating['scale_max']:
                        errors.append(path + '/ratings: value exceeds scale_max')
            if 'attributes' in value:
                scales = set()
                for attr in value['attributes']:
                    key = attr['scale_id']
                    if key in scales:
                        errors.append(path + '/attributes: duplicate scale_id ' + key)
                    scales.add(key)
                    scale = tables['attribute_scales'].get(key)
                    if scale and attr['value'] is not None:
                        if not scale['minimum'] <= attr['value'] <= scale['maximum']:
                            errors.append(path + '/attributes: value outside scale ' + key)
            if 'record' in value:
                record = value['record']
                created = datetime.fromisoformat(record['created_at'].replace('Z', '+00:00'))
                updated = datetime.fromisoformat(record['updated_at'].replace('Z', '+00:00'))
                if updated < created:
                    errors.append(path + '/record: updated_at precedes created_at')
                if record['status'] == 'ready':
                    prov = record['provenance']
                    if not prov['source_ids'] or prov['verification'] not in ('human_verified', 'source_verified'):
                        errors.append(path + '/record: ready requires reviewed provenance with a source')

    walk(data)
    for row in data['attribute_scales']:
        levels = [item['value'] for item in row['levels']]
        if row['maximum'] <= row['minimum'] or len(levels) != len(set(levels)):
            errors.append(f"scale {row['id']}: invalid limits or duplicate levels")
        if any(not row['minimum'] <= number <= row['maximum'] for number in levels):
            errors.append(f"scale {row['id']}: level outside limits")

    def parent_segment(segment_id, episode_id, label):
        segment = tables['segments'].get(segment_id)
        if segment and segment['episode_id'] != episode_id:
            errors.append(label + ': segment belongs to another episode')

    def interval(start, end, duration, label):
        if end is not None and end <= start:
            errors.append(label + ': end must be greater than start')
        if duration is not None and (start >= duration or (end is not None and end > duration)):
            errors.append(label + ': interval exceeds known duration')

    segment_positions = set()
    order_positions = set()
    for row in data['episodes']:
        season = tables['seasons'].get(row['season_id'])
        if season and season['series_id'] != row['series_id']:
            errors.append(f"episode {row['id']}: season belongs to another series")
        schemes = [item['scheme'] for item in row['orders']]
        if len(schemes) != len(set(schemes)):
            errors.append(f"episode {row['id']}: duplicate order scheme")
        for order in row['orders']:
            key = (row['series_id'], row['season_id'], order['scheme'], order['position'])
            if key in order_positions:
                errors.append(f"episode {row['id']}: duplicate position in same season/order scheme")
            order_positions.add(key)
        if any(link['episode_id'] == row['id'] for link in row['links']):
            errors.append(f"episode {row['id']}: self-reference in links")
    for row in data['segments']:
        key = (row['episode_id'], row['position'])
        if key in segment_positions:
            errors.append(f"segment {row['id']}: duplicate position in episode")
        segment_positions.add(key)
        start, end = row['episode_start_ms'], row['episode_end_ms']
        if (start is None) != (end is None):
            errors.append(f"segment {row['id']}: logical episode timestamps must both be null or known")
        elif start is not None:
            duration = tables['episodes'].get(row['episode_id'], {}).get('duration_ms')
            interval(start, end, duration, 'segment ' + row['id'])
    for row in data['media_assets']:
        if row['storage']['provider'] == 'local':
            if row['storage']['drive_file_id'] is not None or row['storage']['drive_folder_id'] is not None:
                errors.append(f"asset {row['id']}: local provider cannot have Drive IDs")
        tech = row['technical']
        if tech['has_audio'] is False and tech['audio_streams']:
            errors.append(f"asset {row['id']}: has_audio=false conflicts with audio streams")
        indexes = [item['stream_index'] for item in tech['audio_streams']]
        if len(indexes) != len(set(indexes)):
            errors.append(f"asset {row['id']}: duplicate audio stream index")
        for coverage in row['coverage']:
            parent_segment(coverage['segment_id'], coverage['episode_id'], 'asset ' + row['id'])
            interval(coverage['source_in_ms'], coverage['source_out_ms'], row['duration_ms'], 'asset ' + row['id'])
            ep = tables['episodes'].get(coverage['episode_id'])
            source_end = coverage['source_out_ms'] if coverage['source_out_ms'] is not None else row['duration_ms']
            if ep and ep['duration_ms'] is not None and coverage['episode_in_ms'] is not None and source_end is not None:
                if coverage['episode_in_ms'] + source_end - coverage['source_in_ms'] > ep['duration_ms']:
                    errors.append(f"asset {row['id']}: coverage exceeds logical episode duration")
    for row in data['text_tracks']:
        if (row['format'] == 'inline') != (row['external_file'] is None):
            errors.append(f"track {row['id']}: inline requires no external file; other formats require one")
        duration = tables['media_assets'].get(row['media_asset_id'], {}).get('duration_ms')
        starts = [cue['start_ms'] for cue in row['cues']]
        if starts != sorted(starts):
            errors.append(f"track {row['id']}: cues must be sorted by start_ms")
        for cue in row['cues']:
            interval(cue['start_ms'], cue['end_ms'], duration, 'cue ' + cue['id'])
    for row in data['scenes']:
        parent_segment(row['segment_id'], row['episode_id'], 'scene ' + row['id'])
        asset = tables['media_assets'].get(row['media_asset_id'])
        if asset:
            interval(row['start_ms'], row['end_ms'], asset['duration_ms'], 'scene ' + row['id'])
            if not any(part['episode_id'] == row['episode_id'] for part in asset['coverage']):
                errors.append(f"scene {row['id']}: asset has no matching episode coverage")
        for cue_id in row['transcript_cue_ids']:
            cue = tables['cues'].get(cue_id)
            if cue and (cue_asset[cue_id] != row['media_asset_id'] or cue['start_ms'] >= row['end_ms'] or cue['end_ms'] <= row['start_ms']):
                errors.append(f"scene {row['id']}: cue {cue_id} belongs elsewhere or does not overlap")
    return errors


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python validate_catalog.py path/to/catalog.json')
    try:
        data = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
        failures = validate(data)
    except (OSError, ValueError) as error:
        print('ERROR:', error)
        raise SystemExit(1)
    if failures:
        print('\n'.join(failures))
        raise SystemExit(1)
    print('VALID: structure and internal references/timestamps pass; media and factual truth were not verified.')
