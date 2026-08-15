import type { Movie } from '@/types/movie';

const image = (id: string, width = 800) => `https://images.unsplash.com/${id}?auto=format&fit=crop&w=${width}&q=85`;

export const movies: Movie[] = [
  { id: 'the-last-orbit', title: 'The Last Orbit', year: 2026, rating: 8.7, runtime: '2h 14m', genres: ['Sci-Fi', 'Drama'], description: 'A lone astronaut discovers that the signal guiding her home may be the final memory of a world already gone.', poster: image('photo-1446776811953-b23d57bd21aa', 600), backdrop: image('photo-1446776811953-b23d57bd21aa', 1800) },
  { id: 'afterlight', title: 'Afterlight', year: 2025, rating: 8.3, runtime: '1h 58m', genres: ['Drama', 'Mystery'], description: 'In a city where night never ends, a photographer follows one impossible beam of sunlight.', poster: image('photo-1519608487953-e999c86e7453', 600), backdrop: image('photo-1519608487953-e999c86e7453', 1800) },
  { id: 'glass-horizon', title: 'Glass Horizon', year: 2026, rating: 8.1, runtime: '2h 06m', genres: ['Thriller', 'Sci-Fi'], description: 'A brilliant architect is asked to design a city that no one is meant to leave.', poster: image('photo-1500530855697-b586d89ba3ee', 600), backdrop: image('photo-1500530855697-b586d89ba3ee', 1800) },
  { id: 'deep-blue', title: 'Deep Blue', year: 2024, rating: 7.9, runtime: '1h 46m', genres: ['Adventure', 'Drama'], description: 'Two estranged sisters cross an unmapped ocean in search of their father.', poster: image('photo-1518837695005-2083093ee35b', 600), backdrop: image('photo-1518837695005-2083093ee35b', 1800) },
  { id: 'quiet-places', title: 'Quiet Places', year: 2025, rating: 8.5, runtime: '2h 01m', genres: ['Romance', 'Drama'], description: 'A composer returns to the town she fled and finds an old song waiting for her.', poster: image('photo-1470770841072-f978cf4d019e', 600), backdrop: image('photo-1470770841072-f978cf4d019e', 1800) },
  { id: 'nocturne', title: 'Nocturne', year: 2024, rating: 7.8, runtime: '1h 52m', genres: ['Crime', 'Thriller'], description: 'A detective investigates a string of elegant crimes committed at midnight.', poster: image('photo-1478720568477-152d9b164e26', 600), backdrop: image('photo-1478720568477-152d9b164e26', 1800) },
];

export const featuredMovie = movies[0];
