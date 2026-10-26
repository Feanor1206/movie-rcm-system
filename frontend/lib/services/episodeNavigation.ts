import type { CatalogEpisode, CatalogSeason } from './catalogService';

function seasonNumber(season: CatalogSeason): number {
  return season.number ?? season.seasonNumber ?? Number.MAX_SAFE_INTEGER;
}

function episodeNumber(episode: CatalogEpisode): number {
  return episode.number ?? episode.episodeNumber ?? Number.MAX_SAFE_INTEGER;
}

export function sortCatalogSeasons(seasons: CatalogSeason[]): CatalogSeason[] {
  return [...seasons].sort((a, b) => seasonNumber(a) - seasonNumber(b) || a.id.localeCompare(b.id));
}

export function sortCatalogEpisodes(episodes: CatalogEpisode[]): CatalogEpisode[] {
  return [...episodes].sort((a, b) => episodeNumber(a) - episodeNumber(b) || a.id.localeCompare(b.id));
}

export function getEpisodesForSeason(
  episodes: CatalogEpisode[],
  seasonId: string | null,
  hasSeasons = true
): CatalogEpisode[] {
  const filtered = hasSeasons
    ? episodes.filter((episode) => episode.seasonId === seasonId)
    : episodes;
  return sortCatalogEpisodes(filtered);
}

export function getInitialSeasonId(
  seasons: CatalogSeason[],
  episodes: CatalogEpisode[],
  targetEpisodeId?: string | null
): string | null {
  const orderedSeasons = sortCatalogSeasons(seasons);
  if (targetEpisodeId) {
    const target = episodes.find((episode) => episode.id === targetEpisodeId);
    if (target?.seasonId && orderedSeasons.some((season) => season.id === target.seasonId)) {
      return target.seasonId;
    }
  }
  return orderedSeasons[0]?.id ?? null;
}

export function getInitialEpisode(
  episodes: CatalogEpisode[],
  seasonId: string | null,
  targetEpisodeId?: string | null,
  hasSeasons = true
): CatalogEpisode | null {
  const seasonEpisodes = getEpisodesForSeason(episodes, seasonId, hasSeasons);
  const target = targetEpisodeId && seasonEpisodes.find((episode) => episode.id === targetEpisodeId);
  return target || seasonEpisodes[0] || null;
}

export function getAdjacentEpisode(
  episodes: CatalogEpisode[],
  seasonId: string | null,
  currentEpisodeId: string | null,
  direction: -1 | 1,
  hasSeasons = true
): CatalogEpisode | null {
  const seasonEpisodes = getEpisodesForSeason(episodes, seasonId, hasSeasons);
  const currentIndex = seasonEpisodes.findIndex((episode) => episode.id === currentEpisodeId);
  if (currentIndex < 0) return null;
  return seasonEpisodes[currentIndex + direction] ?? null;
}
