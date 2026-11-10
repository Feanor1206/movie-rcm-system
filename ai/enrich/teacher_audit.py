import argparse
import json
import random
import re
import sqlite3
from pathlib import Path

from .common import CATALOG, episodes, pilot_options, read, write


def contains(text, name):
    return bool(name and re.search(r'(?<!\w)' + re.escape(name) + r'(?!\w)', text, re.IGNORECASE))


def scene_audit(directory, row, scene, characters):
    cues = [cue for cue in read(directory / 'asr.json')['cues']
            if cue['start_ms'] < scene['end_ms'] and cue['end_ms'] > scene['start_ms']]
    frames = [frame for frame in read(directory / 'keyframes.json')['frames']
              if frame['episode_id'] == row['episode_id'] and frame['media_asset_id'] == row['media_asset_id']
              and scene['start_ms'] <= frame['source_ms'] < scene['end_ms']]
    frames.sort(key=lambda frame: frame['source_ms'])
    paths = [str((directory / f['path']).resolve()) for f in frames]
    paths = [paths[0], paths[-1]] if len(paths) > 1 else paths
    text = ' '.join(str(scene.get(field, '')) for field in ('title', 'summary', 'visual_description'))
    text += ' ' + ' '.join(value for field in ('visual_tags', 'sound_events', 'keywords', 'themes')
                            for value in scene.get(field, []))
    cue_text = ' '.join(cue['text'] for cue in cues)
    absent = []
    known_ids = {char['id'] for char in characters}
    for character in characters:
        aliases = [character['name']] + [alias if isinstance(alias, str) else alias.get('text', '')
                                         for alias in character.get('aliases', [])]
        mentioned = character['id'] in scene.get('character_ids', []) or any(contains(text, a) for a in aliases)
        if mentioned and not any(contains(cue_text, a) for a in aliases):
            absent.append(character['name'])
    absent.extend('unknown ID: ' + value for value in scene.get('character_ids', []) if value not in known_ids)
    catalog_names = [name for char in characters for name in [char['name']] +
                     [alias if isinstance(alias, str) else alias.get('text', '') for alias in char.get('aliases', [])]]
    for name in scene.get('reported_character_names', []):
        if not any(name.casefold() == alias.casefold() for alias in catalog_names) or not contains(cue_text, name):
            absent.append(name)
    return {'scene_id': scene['scene_id'], 'keyframe_paths': paths, 'cues': cues,
            'caption': {key: scene[key] for key in ('title', 'summary', 'visual_description', 'character_ids') if key in scene} or None,
            'caption_status': 'available' if 'title' in scene else 'absent', 'absent_names': sorted(set(absent))}


def main():
    parser = argparse.ArgumentParser(description='Audit teacher outputs and select reproducible scene samples.')
    pilot_options(parser)
    parser.add_argument('--catalog', type=Path, default=CATALOG)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    catalog = read(args.catalog)
    series = {episode['id']: episode['series_id'] for episode in catalog['episodes']}
    scenes = []
    for row in episodes(args.inventory, args.episode):
        directory = args.artifacts / row['episode_id']
        characters = [char for char in catalog['characters'] if series[row['episode_id']] in char.get('series_ids', [])]
        captions = read(directory / 'captions.json')['scenes'] if (directory / 'captions.json').exists() else []
        by_id = {scene['scene_id']: scene for scene in captions}
        for scene in read(directory / 'scenes.json')['scenes']:
            item = scene_audit(directory, row, {**scene, **by_id.get(scene['scene_id'], {})}, characters)
            scenes.append({'episode_id': row['episode_id'], **item})
    db_path = args.artifacts / 'teacher_budget.sqlite3'
    requests = images = 0
    provider_responses = []
    if db_path.exists():
        with sqlite3.connect(db_path) as db:
            requests, images = db.execute('SELECT COUNT(*), COALESCE(SUM(image_count), 0) FROM requests WHERE run_id = ?', (args.run_id,)).fetchone()
            provider_responses = [{'usage': json.loads(usage) if usage is not None else None,
                                   'cost': json.loads(cost) if cost is not None else None}
                                  for usage, cost in db.execute('SELECT usage_json, cost_json FROM requests WHERE run_id = ?', (args.run_id,))]
    rng = random.Random(20261110)
    sample = rng.sample(scenes, min(10, len(scenes)))
    report = {'run_id': args.run_id, 'request_attempts': requests, 'images_in_attempts': images,
              'provider_responses': provider_responses, 'flagged_scenes': [scene for scene in scenes if scene['absent_names']],
              'sample_seed': 20261110, 'sample': sample}
    write(args.output, report)
    print(json.dumps({'output': str(args.output), 'request_attempts': requests, 'images_in_attempts': images,
                      'scenes': len(scenes), 'sample': len(sample), 'flagged_scenes': len(report['flagged_scenes'])}))


if __name__ == '__main__':
    main()
