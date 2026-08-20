import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getActiveProcesses } from '../api';

/** How often the caller asks whether the job is still going. */
const JOB_POLL_MS = 2000;

export interface ClipJobOutcome {
  ok: boolean;
  message: string;
}

interface UseClipJobOptions {
  /** Registers the job on the backend and answers with the key to watch. */
  begin: () => Promise<string>;
  /**
   * Asked once that key has left the list, and what it answers is what gets
   * reported. The job leaves `/active_processes` whether it worked or not, so
   * this is where the difference is established — from the refreshed project,
   * not from the fact that the key is gone.
   */
  settle: () => Promise<ClipJobOutcome>;
  /** Told what happened, once there is something to say. */
  onFinished: (outcome: ClipJobOutcome) => void;
  /** What to say when the job could not even be started. */
  startFailure: string;
}

/**
 * `fetch` rejects with `TypeError: Failed to fetch` for a dropped connection, a
 * DNS failure and a CORS rejection alike, which tells the user nothing they can
 * act on. Anything the API itself produced is already a written sentence and is
 * passed through untouched.
 */
export const describeRequestFailure = (error: unknown, fallback: string): string => {
  if (error instanceof TypeError) {
    return 'Could not reach the server. Check that the backend is running, then try again.';
  }
  return error instanceof Error && error.message ? error.message : fallback;
};

/**
 * Starting one long job on a clip, and watching it until there is something to
 * report.
 *
 * The work runs on the backend and outlives whatever started it — an encode
 * takes longer than a browser will hold a request open — so what is held here
 * is a key to watch rather than a promise to await: the job is registered,
 * `/active_processes` is polled until the key leaves it, and the refreshed
 * project is what says what came of it.
 *
 * Shared by re-cutting a clip and by publishing one, which now begins with the
 * same cut.
 */
export const useClipJob = ({ begin, settle, onFinished, startFailure }: UseClipJobOptions) => {
  const queryClient = useQueryClient();
  const [job, setJob] = useState<{ key: string; startedAt: number } | null>(null);
  const finishing = useRef(false);
  // Held in refs so a caller passing inline functions does not re-arm the
  // effect below on every one of its own renders.
  const settleRef = useRef(settle);
  settleRef.current = settle;
  const onFinishedRef = useRef(onFinished);
  onFinishedRef.current = onFinished;
  const beginRef = useRef(begin);
  beginRef.current = begin;

  // Only while something is being watched: this endpoint is otherwise polled by
  // the project page, and nothing else here has a reason to add to it.
  const { data: processes, dataUpdatedAt } = useQuery({
    queryKey: ['activeProcesses'],
    queryFn: getActiveProcesses,
    enabled: !!job,
    refetchInterval: JOB_POLL_MS,
  });

  useEffect(() => {
    if (!job || !processes) return;
    // A cached list fetched before this job was registered says nothing about
    // it. Without this the very first poll can read a stale snapshot and call
    // the job finished the moment it starts.
    if (dataUpdatedAt < job.startedAt) return;
    if (processes.includes(job.key)) return;
    // The effect can run again while the refetch below is in flight, and
    // finishing twice would report the outcome twice.
    if (finishing.current) return;
    finishing.current = true;

    void (async () => {
      setJob(null);
      onFinishedRef.current(await settleRef.current());
      finishing.current = false;
    })();
  }, [job, processes, dataUpdatedAt]);

  const start = async () => {
    if (job) return;
    try {
      const key = await beginRef.current();
      setJob({ key, startedAt: Date.now() });
      // The list about to be polled may already be cached from before the job
      // existed.
      queryClient.invalidateQueries({ queryKey: ['activeProcesses'] });
    } catch (error) {
      onFinishedRef.current({
        ok: false,
        message: describeRequestFailure(error, startFailure),
      });
    }
  };

  return { isRunning: !!job, start };
};
