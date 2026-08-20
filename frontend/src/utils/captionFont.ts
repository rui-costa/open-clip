import { useEffect, useState } from 'react';
import { getCaptionFontUrl, type CaptionFont } from '../api';

/**
 * Loads the font file the clipper will burn with, so the preview draws the
 * captions in the same typeface libass will.
 *
 * A family name is not enough on its own: "Arial Black" means one file on the
 * machine running the browser and, when the backend is in a container, a
 * different one on the machine doing the render — often a metric-compatible
 * substitute with different glyph shapes. The backend resolves the face and
 * serves that exact file; this loads it under a private family name so nothing
 * on the page can shadow it.
 */

// One FontFace per URL, shared by every clip card. Twenty cards asking for the
// same face should not mean twenty downloads and twenty entries in
// `document.fonts`.
const loaded = new Map<string, Promise<string>>();

const familyFor = (url: string) => `OpenClipCaption-${btoa(url).replace(/[^a-zA-Z0-9]/g, '')}`;

const load = (path: string): Promise<string> => {
  const cached = loaded.get(path);
  if (cached) return cached;

  const family = familyFor(path);
  const pending = (async () => {
    // Weight and slant are baked into the file the backend matched, so the face
    // is registered as a plain regular one. Asking the browser for bold on top
    // of an already-bold file is what produces a faux-bold the render will not
    // have.
    const face = new FontFace(family, `url(${getCaptionFontUrl(path)})`, {
      weight: 'normal',
      style: 'normal',
    });
    await face.load();
    document.fonts.add(face);
    return family;
  })();

  loaded.set(path, pending);
  // A failed load must not poison the cache: the next card should try again
  // rather than inherit the rejection.
  pending.catch(() => loaded.delete(path));
  return pending;
};

/**
 * The family name to render captions with: the loaded face once it is ready,
 * and `null` until then (or if it cannot be loaded), which callers fall back
 * from to the style's own family name.
 */
export const useCaptionFont = (font: CaptionFont | undefined): string | null => {
  const path = font?.url ?? null;
  const [family, setFamily] = useState<string | null>(null);

  useEffect(() => {
    if (!path || typeof FontFace === 'undefined') {
      setFamily(null);
      return;
    }
    let active = true;
    load(path)
      .then((name) => {
        if (active) setFamily(name);
      })
      .catch(() => {
        if (active) setFamily(null);
      });
    return () => {
      active = false;
    };
  }, [path]);

  return family;
};
