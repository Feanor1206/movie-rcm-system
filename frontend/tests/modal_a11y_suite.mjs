import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const root = path.resolve(__dirname, '..');

// Read source files directly to verify accessibility attributes and structural invariants
const authModalSource = fs.readFileSync(path.join(root, 'features/auth/components/AuthModal.tsx'), 'utf8');
const movieDetailSource = fs.readFileSync(path.join(root, 'features/movies/components/MovieDetail.tsx'), 'utf8');
const cinebotSource = fs.readFileSync(path.join(root, 'features/chat/components/CineBot.tsx'), 'utf8');

test('1. AuthModal: Accessibility attributes, focus trapping, opener restoration, and >=44px touch targets', () => {
  // role and aria attributes
  assert.ok(authModalSource.includes('role="dialog"'), 'AuthModal must declare role="dialog"');
  assert.ok(authModalSource.includes('aria-modal="true"'), 'AuthModal must declare aria-modal="true"');
  assert.ok(authModalSource.includes('aria-labelledby="auth-modal-title"'), 'AuthModal must have aria-labelledby');

  // Initial focus
  assert.ok(authModalSource.includes('firstInputRef.current?.focus()'), 'AuthModal must auto-focus first input');

  // Opener guard (must not recapture internal element on re-render)
  assert.ok(
    authModalSource.includes('!modalRef.current.contains(document.activeElement)'),
    'AuthModal must guard opener capture against internal elements'
  );

  // Focus trap (Tab and Shift+Tab)
  assert.ok(authModalSource.includes("e.key === 'Tab'"), 'AuthModal must intercept Tab key');
  assert.ok(authModalSource.includes('e.shiftKey'), 'AuthModal must handle Shift+Tab reverse cycle');
  assert.ok(authModalSource.includes('lastElement.focus()'), 'AuthModal must wrap to lastElement on Shift+Tab');
  assert.ok(authModalSource.includes('firstElement.focus()'), 'AuthModal must wrap to firstElement on Tab');

  // Escape key close & focus restore
  assert.ok(authModalSource.includes("e.key === 'Escape'"), 'AuthModal must close on Escape key');
  assert.ok(authModalSource.includes('openerRef.current?.focus()'), 'AuthModal must restore focus to opener on unmount/close');

  // Close button >= 44x44px touch target
  assert.ok(
    authModalSource.includes('min-h-[44px]') && authModalSource.includes('min-w-[44px]'),
    'AuthModal close button must specify >= 44x44px touch target'
  );
});

test('2. MovieDetail Video Player Modal: Accessibility, initial focus, Tab trapping, opener restore, and touch targets', () => {
  // role and aria attributes
  assert.ok(movieDetailSource.includes('role="dialog"'), 'Video player modal must declare role="dialog"');
  assert.ok(movieDetailSource.includes('aria-modal="true"'), 'Video player modal must declare aria-modal="true"');

  // Initial focus inside modal
  assert.ok(
    movieDetailSource.includes('focusable[0].focus()'),
    'Video player modal must set initial focus inside modal'
  );

  // Focus trap
  assert.ok(movieDetailSource.includes("e.key === 'Tab'"), 'Video player must intercept Tab key');
  assert.ok(
    movieDetailSource.includes('!videoModalRef.current.contains(document.activeElement)'),
    'Video player must trap focus if focus is outside modal'
  );

  // Escape key & opener restore
  assert.ok(movieDetailSource.includes("e.key === 'Escape'"), 'Video player must close on Escape');
  assert.ok(
    movieDetailSource.includes('playerOpenerRef.current') && movieDetailSource.includes('?.focus()'),
    'Video player must restore focus to opener on close'
  );

  // Close button touch target >= 44x44px
  assert.ok(
    movieDetailSource.includes('aria-label="Đóng trình phát"') &&
    movieDetailSource.includes('min-h-[44px]') &&
    movieDetailSource.includes('min-w-[44px]'),
    'Video player close button must be >= 44x44px'
  );

  // Trailer button touch target min-h >= 44px
  assert.ok(
    movieDetailSource.includes('btn-primary min-h-[44px]'),
    'Xem trailer button must declare min-h-[44px]'
  );
});

test('3. CineBot Shell: Reduced motion JS policy, focus trap, opener restoration, and touch targets', () => {
  // role and aria attributes
  assert.ok(cinebotSource.includes('role="dialog"'), 'CineBot must declare role="dialog"');
  assert.ok(cinebotSource.includes('aria-modal="true"'), 'CineBot must declare aria-modal="true"');

  // Reduced motion policy in scrollToBottom
  assert.ok(
    cinebotSource.includes('(prefers-reduced-motion: reduce)'),
    'CineBot must query prefers-reduced-motion in JS'
  );
  assert.ok(
    cinebotSource.includes("behavior: isReduced ? 'auto' : 'smooth'"),
    'CineBot scrollToBottom must switch to auto when reduced motion is preferred'
  );

  // Initial focus & Opener restoration
  assert.ok(cinebotSource.includes('inputRef.current?.focus()'), 'CineBot must focus input on open');
  assert.ok(cinebotSource.includes('openerRef.current?.focus()'), 'CineBot must restore opener focus on close');

  // Tab focus trap
  assert.ok(cinebotSource.includes("e.key === 'Tab'"), 'CineBot must intercept Tab key');
  assert.ok(
    cinebotSource.includes('!cinebotRef.current.contains(document.activeElement)'),
    'CineBot must keep focus trapped inside dialog'
  );

  // Header buttons touch targets
  assert.ok(
    cinebotSource.includes('aria-label="Đóng CineBot"') &&
    cinebotSource.includes('min-h-[44px]') &&
    cinebotSource.includes('min-w-[44px]'),
    'CineBot close button must be >= 44x44px'
  );

  // Floating trigger button touch target and responsive position
  assert.ok(
    cinebotSource.includes('min-h-[44px]') && cinebotSource.includes('min-w-[44px]'),
    'CineBot floating trigger must be >= 44x44px'
  );
  assert.ok(
    cinebotSource.includes('bottom-4 right-4 sm:bottom-6 sm:right-6'),
    'CineBot floating trigger must use responsive safe positioning on mobile'
  );
});
