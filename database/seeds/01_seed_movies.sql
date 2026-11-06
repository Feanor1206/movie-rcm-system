-- ==========================================================
-- SEED DATA: 6 MOVIES WITH LOCAL VIDEO URLS
-- ==========================================================

INSERT INTO movies (id, title, release_year, rating, runtime, genres, description, poster, backdrop, video_url) VALUES
('the-last-orbit', 'The Last Orbit', 2026, 8.7, '2h 14m', 'Sci-Fi,Drama', 
 'A lone astronaut discovers that the signal guiding her home may be the final memory of a world already gone.', 
 'https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?auto=format&fit=crop&w=600&q=85', 
 'https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?auto=format&fit=crop&w=1800&q=85', 
 '/videos/the-last-orbit.mp4'),

('afterlight', 'Afterlight', 2025, 8.3, '1h 58m', 'Drama,Mystery', 
 'In a city where night never ends, a photographer follows one impossible beam of sunlight.', 
 'https://images.unsplash.com/photo-1519608487953-e999c86e7453?auto=format&fit=crop&w=600&q=85', 
 'https://images.unsplash.com/photo-1519608487953-e999c86e7453?auto=format&fit=crop&w=1800&q=85', 
 '/videos/afterlight.mp4'),

('glass-horizon', 'Glass Horizon', 2026, 8.1, '2h 06m', 'Thriller,Sci-Fi', 
 'A brilliant architect is asked to design a city that no one is meant to leave.', 
 'https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=600&q=85', 
 'https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1800&q=85', 
 '/videos/glass-horizon.mp4'),

('deep-blue', 'Deep Blue', 2024, 7.9, '1h 46m', 'Adventure,Drama', 
 'Two estranged sisters cross an unmapped ocean in search of their father.', 
 'https://images.unsplash.com/photo-1518837695005-2083093ee35b?auto=format&fit=crop&w=600&q=85', 
 'https://images.unsplash.com/photo-1518837695005-2083093ee35b?auto=format&fit=crop&w=1800&q=85', 
 '/videos/deep-blue.mp4'),

('quiet-places', 'Quiet Places', 2025, 8.5, '2h 01m', 'Romance,Drama', 
 'A composer returns to the town she fled and finds an old song waiting for her.', 
 'https://images.unsplash.com/photo-1470770841072-f978cf4d019e?auto=format&fit=crop&w=600&q=85', 
 'https://images.unsplash.com/photo-1470770841072-f978cf4d019e?auto=format&fit=crop&w=1800&q=85', 
 '/videos/quiet-places.mp4'),

('nocturne', 'Nocturne', 2024, 7.8, '1h 52m', 'Crime,Thriller', 
 'A detective investigates a string of elegant crimes committed at midnight.', 
 'https://images.unsplash.com/photo-1478720568477-152d9b164e26?auto=format&fit=crop&w=600&q=85', 
 'https://images.unsplash.com/photo-1478720568477-152d9b164e26?auto=format&fit=crop&w=1800&q=85', 
 '/videos/nocturne.mp4')
ON CONFLICT (id) DO NOTHING;
