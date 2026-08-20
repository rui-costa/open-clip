import { useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { regenerateClip, type ProjectMetadata } from '../api';
import { useClipJob, type ClipJobOutcome } from './useClipJob';

export type ClipRenderOutcome = ClipJobOutcome;

export { describeRequestFailure } from './useClipJob';

interface UseClipRenderOptions {
  projectId: string;
  clipIndex: number;
  /**
   * When the current file was written, which is how a finished re-cut is told
   * from one that fell over: the job leaves `/active_processes` either way.
   */
  renderedAt?: string | null;
  /** Told what happened, once the refreshed project says. */
  onFinished: (outcome: ClipRenderOutcome) => void;
}

/**
 * Re-cutting one clip, and watching it until there is something to report.
 *
 * Shared by the clip detail page and the grid card, which is what keeps the two
 * agreeing about when a render is running and what "finished" means.
 */
export const useClipRender = ({
  projectId,
  clipIndex,
  renderedAt,
  onFinished,
}: UseClipRenderOptions) => {
  const queryClient = useQueryClient();
  // The stamp the file carried when the job started. A finished job that did
  // not move this on did not produce a file.
  const renderedAtBefore = useRef<string | null>(null);

  const { isRunning, start } = useClipJob({
    begin: async () => {
      renderedAtBefore.current = renderedAt ?? null;
      const { job } = await regenerateClip(projectId, clipIndex);
      return job;
    },
    settle: async () => {
      // Awaited rather than fired and forgotten: the answer to "did it work"
      // is in the refreshed project, so there is nothing to say until it lands.
      await queryClient.invalidateQueries({ queryKey: ['project', projectId] });
      queryClient.invalidateQueries({ queryKey: ['projectMetadata', projectId] });
      queryClient.invalidateQueries({ queryKey: ['clipCaptions', projectId] });

      const fresh = queryClient.getQueryData<ProjectMetadata>(['project', projectId]);
      const stamp = fresh?.highlights?.[clipIndex]?.rendered_at ?? null;
      return stamp && stamp !== renderedAtBefore.current
        ? { ok: true, message: 'Clip re-rendered with the current settings.' }
        : {
            ok: false,
            message:
              'The render stopped without producing a file. The backend log has what ffmpeg reported.',
          };
    },
    onFinished,
    startFailure: 'The render could not be started.',
  });

  return { isRendering: isRunning, start };
};
