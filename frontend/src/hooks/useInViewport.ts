import { useEffect, useRef, useState } from 'react';

/**
 * Whether the element has ever come near the viewport.
 *
 * Latches on rather than tracking visibility both ways: this gates whether a
 * `<video>` is mounted at all, and unmounting one that had scrolled off would
 * stop playback and throw away everything the browser had buffered.
 *
 * Falls back to "always visible" where IntersectionObserver is missing, so the
 * absence of the API costs eager loading rather than a blank card.
 */
export const useInViewport = <T extends Element>(
  rootMargin = '400px'
): [React.RefObject<T | null>, boolean] => {
  const ref = useRef<T>(null);
  const [hasApproached, setHasApproached] = useState(
    () => typeof IntersectionObserver === 'undefined'
  );

  useEffect(() => {
    if (hasApproached) return;
    const element = ref.current;
    if (!element) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) setHasApproached(true);
      },
      // Margin rather than zero: the player should be ready by the time it is
      // scrolled to, not start loading once it is already on screen.
      { rootMargin }
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [hasApproached, rootMargin]);

  return [ref, hasApproached];
};
