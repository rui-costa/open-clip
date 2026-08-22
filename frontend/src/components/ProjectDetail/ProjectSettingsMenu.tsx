import React, { useEffect, useId, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CaptionStyler } from '../ClipManagement/CaptionStyler';
import { OverlayStyler } from '../ClipManagement/OverlayStyler';
import { DescriptionPanel } from './DescriptionPanel';
import {
  getAspectRatioMap,
  getResolutionMap,
  updateProjectSettings,
  type ClipPreview,
  type ProjectMetadata,
} from '../../api';

/** The three project settings edited in place, in the menu. */
type ProjectSettings = { resolution?: string; aspect_ratio?: string; clip_preview?: ClipPreview };

/**
 * One in-flight save. The label is carried along so a failure can name the
 * setting that failed: one mutation serves all three controls, and "could not
 * save that setting" left the user to re-check every one of them.
 */
type SettingsChange = { label: string; settings: ProjectSettings };

/** `source` minus every key `remove` mentions. */
const without = (source: ProjectSettings, remove: ProjectSettings): ProjectSettings => {
  const next = { ...source };
  (Object.keys(remove) as (keyof ProjectSettings)[]).forEach((key) => delete next[key]);
  return next;
};

interface ProjectSettingsMenuProps {
  metadata: ProjectMetadata;
}

/**
 * Everything that applies to every clip at once: what the clipper renders at,
 * what it burns in, what the upload says, and what the grid shows at rest.
 *
 * In the header with the other project actions rather than on the page. These
 * change the project, not anything you can see — and they are set once and
 * rarely revisited, which is the opposite of what a permanent row across the
 * page claims about a control.
 */
export const ProjectSettingsMenu: React.FC<ProjectSettingsMenuProps> = ({ metadata }) => {
  const queryClient = useQueryClient();
  const resolutionId = useId();
  const aspectRatioId = useId();
  const clipPreviewId = useId();
  const errorId = useId();

  const { data: resolutionsData } = useQuery({ queryKey: ['resolutions'], queryFn: getResolutionMap });
  const { data: aspectRatiosData } = useQuery({ queryKey: ['aspectRatios'], queryFn: getAspectRatioMap });

  // What the user picked, held until the project comes back saying the same
  // thing. Without this the select's value reads from the metadata, so between
  // the change and the refetch it snapped back to the old option — which reads
  // as the app refusing the change rather than saving it.
  const [pendingSettings, setPendingSettings] = useState<ProjectSettings>({});

  const settingsMutation = useMutation({
    mutationFn: ({ settings }: SettingsChange) => updateProjectSettings(metadata.project_id, settings),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project', metadata.project_id] });
      queryClient.invalidateQueries({ queryKey: ['projectMetadata', metadata.project_id] });
    },
    // A save that failed changed nothing on the server, so the control has to
    // stop showing the value it failed to store.
    onError: (_error, variables) => setPendingSettings((prev) => without(prev, variables.settings)),
  });

  const saveSetting = (label: string, settings: ProjectSettings) => {
    setPendingSettings((prev) => ({ ...prev, ...settings }));
    settingsMutation.mutate({ label, settings });
  };

  // Which control the standing error belongs to, so the message can name it and
  // the control itself can point at the message.
  const failedSetting = settingsMutation.isError ? settingsMutation.variables?.label : undefined;

  // A pending pick is retired the moment the project comes back carrying it,
  // rather than when the request returns: the mutation resolves before the
  // refetch it triggers, and clearing on the response put the old value back
  // on screen for as long as the refetch took.
  const storedSettings = metadata.settings;
  useEffect(() => {
    setPendingSettings((prev) => {
      const settled = (Object.keys(prev) as (keyof ProjectSettings)[]).filter(
        (key) => storedSettings?.[key] === prev[key]
      );
      return settled.length ? without(prev, Object.fromEntries(settled.map((k) => [k, prev[k]]))) : prev;
    });
  }, [storedSettings]);

  // These option lists arrive from their own queries, so on first paint — and
  // for good if the request fails — the map is empty. A select whose value has
  // no matching option displays the first one instead, which told the user the
  // project was on "keep original" when it was not. The stored value is always
  // offered, whether or not the map has caught up.
  const optionsFor = (map: Record<string, string> | undefined, current: string) => {
    const keys = Object.keys(map ?? {});
    return keys.includes(current) || current === 'keep original' ? keys : [current, ...keys];
  };

  // `||` rather than `??` on the stored value: a project saved with an empty
  // string means "keep original" too.
  const currentResolution = pendingSettings.resolution || storedSettings?.resolution || 'keep original';
  const currentAspectRatio = pendingSettings.aspect_ratio || storedSettings?.aspect_ratio || 'keep original';
  const currentClipPreview: ClipPreview =
    (pendingSettings.clip_preview ?? storedSettings?.clip_preview) === 'video' ? 'video' : 'thumbnail';

  return (
    // `aria-busy` rather than `disabled` on the controls. Disabling the select
    // the user is currently in hands focus back to the document body — a
    // keyboard user is returned to the top of the page for having changed a
    // setting — and it deadened the other two along with it, because one
    // mutation serves all three.
    <div aria-busy={settingsMutation.isPending}>
      <div className="options-bar options-bar--stacked">
        <div className="options-bar__group">
          <span className="options-bar__setting">
            <label htmlFor={resolutionId}>Resolution:</label>
            <select
              id={resolutionId}
              className="options-bar__select"
              value={currentResolution}
              aria-describedby={failedSetting === 'resolution' ? errorId : undefined}
              onChange={(e) => saveSetting('resolution', { resolution: e.target.value })}
            >
              <option value="keep original">Keep original</option>
              {/* Not uppercased: these are format names, and "1080P" is not
                  how anyone writes 1080p. */}
              {optionsFor(resolutionsData, currentResolution).map((opt) => (
                <option key={opt} value={opt}>{opt}</option>
              ))}
            </select>
          </span>

          <span className="options-bar__setting">
            <label htmlFor={aspectRatioId}>Aspect Ratio:</label>
            <select
              id={aspectRatioId}
              className="options-bar__select"
              value={currentAspectRatio}
              aria-describedby={failedSetting === 'aspect ratio' ? errorId : undefined}
              onChange={(e) => saveSetting('aspect ratio', { aspect_ratio: e.target.value })}
            >
              <option value="keep original">Keep original</option>
              {optionsFor(aspectRatiosData, currentAspectRatio).map((opt) => (
                <option key={opt} value={opt}>{opt}</option>
              ))}
            </select>
          </span>

          {/* Not a render setting like the two above — this one changes nothing
              about the files. It sits with them because it is the third thing
              that applies to every clip at once. */}
          <span className="options-bar__setting">
            <label htmlFor={clipPreviewId}>Card preview:</label>
            <select
              id={clipPreviewId}
              className="options-bar__select"
              value={currentClipPreview}
              aria-describedby={failedSetting === 'card preview' ? errorId : undefined}
              onChange={(e) => saveSetting('card preview', { clip_preview: e.target.value as ClipPreview })}
            >
              <option value="thumbnail">Thumbnail</option>
              <option value="video">Video frame</option>
            </select>
          </span>
        </div>

        <div className="options-bar__group">
          <CaptionStyler
            variant="inline"
            projectId={metadata.project_id}
            settings={metadata.settings?.captions}
          />
          <OverlayStyler
            variant="inline"
            projectId={metadata.project_id}
            overlay={metadata.settings?.overlay}
          />
          <DescriptionPanel
            variant="inline"
            projectId={metadata.project_id}
            settings={metadata.settings?.description}
          />
        </div>
      </div>

      {/* 0.8rem, like every other label in the menu. This was the smallest text
          on the page, which is the wrong size for the only text that reports a
          failure. */}
      {settingsMutation.isError && (
        <p
          id={errorId}
          role="alert"
          style={{ margin: 'var(--space-sm) 0 0 0', fontSize: '0.8rem', color: 'var(--error)' }}
        >
          Could not save the {failedSetting ?? 'setting'}:{' '}
          {settingsMutation.error instanceof Error ? settingsMutation.error.message : 'please try again.'}
        </p>
      )}
    </div>
  );
};
