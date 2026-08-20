import { useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { uploadClip, type ProjectMetadata } from '../api';
import { useClipJob, type ClipJobOutcome } from './useClipJob';

interface UseClipUploadOptions {
  projectId: string;
  clipIndex: number;
  /**
   * When this clip was last published, which is how a finished job that put a
   * video up is told from one that did not: the key leaves `/active_processes`
   * either way.
   */
  uploadedAt?: string | null;
  /** Told what happened, once the refreshed project says. */
  onFinished: (outcome: ClipJobOutcome) => void;
}

/**
 * Publishing one clip, and watching it until there is something to report.
 *
 * The upload cuts the clip afresh before it sends anything — what goes to
 * YouTube is the clip as the page shows it, not whatever was rendered before
 * the last change to its captions or its title — so it is an encode followed by
 * an upload, and far longer than a request can be held open. The backend writes
 * the outcome onto the highlight: the published URL, or `upload_error`.
 *
 * Shared by the clip detail page and the grid card, so the two agree about when
 * a clip is going up and what finishing means.
 */
export const useClipUpload = ({
  projectId,
  clipIndex,
  uploadedAt,
  onFinished,
}: UseClipUploadOptions) => {
  const queryClient = useQueryClient();
  // What the highlight said when the job started. A finished job that did not
  // move this on published nothing.
  const uploadedAtBefore = useRef<string | null>(null);

  const { isRunning, start } = useClipJob({
    begin: async () => {
      uploadedAtBefore.current = uploadedAt ?? null;
      const { job } = await uploadClip(projectId, clipIndex);
      return job;
    },
    settle: async () => {
      // Awaited rather than fired and forgotten: the answer to "is it live" is
      // in the refreshed project, so there is nothing to say until it lands.
      // The clip was re-cut on the way, so its file and its captions moved too.
      await queryClient.invalidateQueries({ queryKey: ['project', projectId] });
      queryClient.invalidateQueries({ queryKey: ['projectMetadata', projectId] });
      queryClient.invalidateQueries({ queryKey: ['clipCaptions', projectId] });

      const fresh = queryClient.getQueryData<ProjectMetadata>(['project', projectId]);
      const highlight = fresh?.highlights?.[clipIndex];
      const stamp = highlight?.uploaded_at ?? null;
      if (stamp && stamp !== uploadedAtBefore.current) {
        return { ok: true, message: 'Uploaded to YouTube' };
      }
      return {
        ok: false,
        // Written by whichever part gave up — the render or the upload — and
        // already a sentence, so it is shown as it stands.
        message:
          highlight?.upload_error ||
          'The upload stopped without publishing anything. The backend log has the reason.',
      };
    },
    onFinished,
    startFailure: 'The upload could not be started.',
  });

  return { isUploading: isRunning, start };
};
