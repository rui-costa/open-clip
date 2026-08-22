import { useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { importClipToPostiz, type ProjectMetadata } from '../api';
import { useClipJob, type ClipJobOutcome } from './useClipJob';

interface UseClipPostizOptions {
  projectId: string;
  clipIndex: number;
  /**
   * When this clip was last imported, which is how a finished import job is
   * told from one that gave up: the job leaves `/active_processes` either way.
   */
  importedAt?: string | null;
  /** Told what happened, once the refreshed project says. */
  onFinished: (outcome: ClipJobOutcome) => void;
}

/**
 * Importing one clip into Postiz, and watching it until there is something to
 * report.
 *
 * Shaped like `useClipUpload` because the backend job is: the import re-cuts
 * the clip first, which outlives a browser request, so what is held is a key to
 * watch rather than a promise to await.
 */
export const useClipPostiz = ({
  projectId,
  clipIndex,
  importedAt,
  onFinished,
}: UseClipPostizOptions) => {
  const queryClient = useQueryClient();
  // What the highlight said when the job started. A finished job that did not
  // move this on filed nothing.
  const importedAtBefore = useRef<string | null>(null);

  const { isRunning, start } = useClipJob({
    begin: async () => {
      importedAtBefore.current = importedAt ?? null;
      const { job } = await importClipToPostiz(projectId, clipIndex);
      return job;
    },
    settle: async () => {
      // Awaited rather than fired and forgotten: the answer to "is it in
      // Postiz" is in the refreshed project, so there is nothing to say until
      // it lands. The clip was re-cut on the way, so its file and its captions
      // moved too.
      await queryClient.invalidateQueries({ queryKey: ['project', projectId] });
      queryClient.invalidateQueries({ queryKey: ['projectMetadata', projectId] });
      queryClient.invalidateQueries({ queryKey: ['clipCaptions', projectId] });

      const fresh = queryClient.getQueryData<ProjectMetadata>(['project', projectId]);
      const highlight = fresh?.highlights?.[clipIndex];
      const stamp = highlight?.postiz_imported_at ?? null;
      if (stamp && stamp !== importedAtBefore.current) {
        const channels = highlight?.postiz_channels ?? [];
        return {
          ok: true,
          // Named rather than counted: which accounts a post is waiting on is
          // the thing worth checking before opening the calendar.
          message: channels.length
            ? `Imported into Postiz for ${channels.map((c) => c.name || c.platform || c.id).join(', ')}`
            : 'Imported into Postiz',
        };
      }
      return {
        ok: false,
        message:
          highlight?.postiz_error ||
          'The import stopped without filing anything. The backend log has the reason.',
      };
    },
    onFinished,
    startFailure: 'The import could not be started.',
  });

  return { isImporting: isRunning, start };
};
