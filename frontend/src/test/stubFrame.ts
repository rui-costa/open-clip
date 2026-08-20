/**
 * jsdom has no layout engine and no ResizeObserver, so anything that sizes
 * itself from its rendered box measures zero and draws nothing. The caption
 * overlay is exactly that, being a percentage of the frame by design, so tests
 * covering it have to stand a frame size in.
 */
export const stubFrameSize = (height = 400, width = 225) => {
  Object.defineProperty(HTMLElement.prototype, 'getBoundingClientRect', {
    configurable: true,
    value: () => ({
      height,
      width,
      top: 0,
      left: 0,
      bottom: height,
      right: width,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    }),
  });

  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    } as unknown as typeof ResizeObserver;
  }
};
