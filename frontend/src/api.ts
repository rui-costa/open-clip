const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

/**
 * A caption style, as resolved by backend/src/services/caption_styles.py.
 *
 * Every size is a percentage of the output frame rather than a pixel value,
 * which is what lets the preview overlay and the burned ASS render agree while
 * drawing at completely different sizes.
 */
export type CaptionStyle = {
  label: string;
  description: string;
  animation: 'karaoke' | 'word' | 'static';
  words_per_cue: number;
  font_family: string;
  font_size_pct: number;
  bold: boolean;
  italic: boolean;
  uppercase: boolean;
  text_color: string;
  active_color: string;
  outline_color: string;
  shadow_color: string;
  box_color: string | null;
  outline_pct: number;
  shadow_pct: number;
  position_pct: number;
  max_width_pct: number;
  active_scale: number;
};

export type CaptionSettings = {
  enabled: boolean;
  preset: string;
  overrides: Partial<CaptionStyle>;
};

export type CaptionWord = { text: string; start: number; end: number };

/** Cue times are relative to the start of the clip, not the source video. */
export type CaptionCue = { start: number; end: number; text: string; words: CaptionWord[] };

/**
 * The face the clipper will burn with, as resolved by fontconfig on the
 * backend. The overlay loads `url` rather than trusting the family name to mean
 * the same thing here as it does there.
 */
export type CaptionFont = {
  family: string;
  /** Ascent-to-descent height per em: the line-height libass will use. */
  height_ratio: number;
  /** Path on this API, or null when the backend could not resolve a file. */
  url: string | null;
};

/**
 * A title drawn over one clip, as stored by backend/src/dataclasses/data.py.
 *
 * Independent of the captions: this is text the user wrote for this clip, shown
 * from `start` (0 by default — the top of the clip) for `duration` seconds and
 * faded out. Times are seconds from the start of the clip. Sizes are
 * percentages of the output frame, the same contract a caption style uses, so
 * the preview overlay and the burned render draw the same thing.
 */
export type OverlayText = {
  enabled: boolean;
  text: string;
  start: number;
  duration: number;
  fade_in: number;
  fade_out: number;
  font_family: string;
  font_size_pct: number;
  bold: boolean;
  italic: boolean;
  uppercase: boolean;
  text_color: string;
  outline_color: string;
  outline_pct: number;
  box_color: string | null;
  /** Distance from the top of the frame, unlike a caption's, measured up from the bottom. */
  position_pct: number;
  max_width_pct: number;
};

/**
 * What a new title starts from, mirroring `OverlayText` in
 * backend/src/dataclasses/data.py.
 *
 * Kept in step by the backend itself: every save comes back sanitized, so a
 * value that drifts here is corrected on the next round trip.
 */
export const DEFAULT_OVERLAY_TEXT: OverlayText = {
  enabled: true,
  text: '',
  start: 0,
  duration: 3,
  // Zero, so the title is fully there on the first frame. A fade in is
  // something to ask for, not something a new title arrives with.
  fade_in: 0,
  fade_out: 0.6,
  font_family: 'Arial Black',
  font_size_pct: 8,
  bold: true,
  italic: false,
  uppercase: true,
  text_color: '#FFFFFF',
  outline_color: '#000000',
  outline_pct: 0.6,
  box_color: null,
  position_pct: 12,
  max_width_pct: 86,
};

/**
 * How one clip's thumbnail is built, as stored by
 * backend/src/dataclasses/data.py.
 *
 * Every field is a departure from a default that already works: the first
 * frame of the clip, no subtitles, and the clip's title over it. A clip whose
 * thumbnail is `null` is not a clip without one — it is a clip using all of
 * those defaults, which is what the clipper renders for it.
 *
 * `frame_time` is seconds from the start of the clip. `extra` is a second
 * piece of text written for the still alone; it never reaches the video.
 */
export type ThumbnailSettings = {
  frame_time: number;
  show_captions: boolean;
  show_overlay: boolean;
  extra: OverlayText | null;
  /** The image last rendered from these settings, or null while there is none. */
  generated_filename: string | null;
  generated_at: string | null;
};

/** What a thumbnail nobody has touched is made of. Mirrors the backend's. */
export const DEFAULT_THUMBNAIL: ThumbnailSettings = {
  frame_time: 0,
  show_captions: false,
  show_overlay: true,
  extra: null,
  generated_filename: null,
  generated_at: null,
};

/**
 * What extra text starts as when it is first added.
 *
 * Mid-frame and smaller than a title. The title is at the top and the captions
 * sit near the bottom, so anything else has to land between them or it draws
 * over one of the two.
 */
export const DEFAULT_THUMBNAIL_EXTRA: OverlayText = {
  ...DEFAULT_OVERLAY_TEXT,
  font_size_pct: 6,
  position_pct: 55,
};

/** One clip's thumbnail as the backend describes it to the page. */
export type ThumbnailPreview = {
  settings: ThumbnailSettings;
  /**
   * The text that will be drawn, worked out by the backend: the clip's own
   * title, or the model's hook standing in for a clip that has none.
   */
  title: OverlayText | null;
  /** The face that title will be burned with. Null when there is no title. */
  title_font: CaptionFont | null;
  /** The clip's length, which is the range a frame can be chosen from. */
  duration: number;
  /** False when no image has been rendered yet, or the file has gone. */
  exists: boolean;
};

export type CaptionPreview = {
  enabled: boolean;
  style: CaptionStyle;
  font: CaptionFont;
  duration: number;
  cues: CaptionCue[];
  /** This clip's title, or null while it has never been given one. */
  overlay: OverlayText | null;
  /** The face the title will be burned with. Null when there is no title. */
  overlay_font: CaptionFont | null;
  /** True when this clip follows the project rather than its own settings. */
  locked: boolean;
  /** The clip's own settings, or null while it is locked to the project. */
  settings: CaptionSettings | null;
};

/**
 * One moment the model picked out of the source.
 *
 * Only the window is guaranteed. Every other field is written by a later
 * pipeline step — the social copy by the video-meta task, the filename by the
 * clipper — so a project that has run the highlights step and nothing else
 * carries highlights with almost all of this missing. They are optional here so
 * that a view reading one has to decide what to show when it is absent, rather
 * than rendering `undefined` as a blank.
 */
export type Highlight = {
  start: number;
  end: number;
  highlight_text?: string;
  viral_hook_text?: string;
  video_title_for_youtube_short?: string;
  /** The model's description of this clip, before the template wraps it. */
  video_description_for_youtube_short?: string;
  video_description_for_x?: string;
  video_description_for_reddit?: string;
  video_description_for_linkedin?: string;
  is_clip_generated?: boolean;
  generated_clip_filename?: string | null;
  /** True when the file's own pixels already carry the captions. */
  captions_burned?: boolean;
  /** The title drawn over this clip, or null/absent for a clip with none. */
  overlay?: OverlayText | null;
  /** True when the file's own pixels already carry that title. */
  overlay_burned?: boolean;
  /** How this clip's thumbnail is built, or null/absent for the defaults. */
  thumbnail?: ThumbnailSettings | null;
  /** When the file was last written. The filename never changes, so this is
   *  what tells a browser holding the previous cut that there is a new one. */
  rendered_at?: string | null;
  /** Where this clip was published, once it has been uploaded to YouTube. */
  youtube_video_id?: string | null;
  youtube_url?: string | null;
  uploaded_at?: string | null;
  /** Why the last publish attempt produced no video, or absent when it did.
   *  The upload runs in the background, so this is where its outcome is read
   *  from rather than from the response to the click that started it. */
  upload_error?: string | null;
};

/**
 * What a project contributes to the YouTube description of its clips.
 *
 * `source_url` is the full episode the shorts were cut from; it becomes a link
 * in every description. It is not YouTube's "Related video" chip, which the
 * Data API cannot set — see `getStudioEditUrl`.
 * Empty `text`/`template` mean "use the application-wide ones".
 */
export type DescriptionSettings = {
  source_url: string;
  source_title: string;
  text: string;
  template: string;
};

/**
 * What an idle clip shows, project-wide.
 *
 * `thumbnail` is the default: a grid of stills is what the shorts will look
 * like in a feed, which is the question a review is asking. `video` leaves the
 * frame the player is parked on, which is what you want while cutting.
 */
export type ClipPreview = 'thumbnail' | 'video';

/** One placeholder a description template may use, as described by the backend. */
export type DescriptionField = { field: string; description: string };

export type ProjectMetadata = {
  project_id: string;
  name: string;
  created_at: string;
  // Cut clips are not a separate array: they are the highlights with
  // `is_clip_generated`, in that order.
  highlights: Highlight[];
  // Output of prompt-defined LLM tasks that have no typed field, keyed by task name.
  llm_outputs?: Record<string, unknown>;
  clips_count?: number;
  step_statuses?: Record<string, string>;
  settings?: {
    resolution?: string;
    aspect_ratio?: string;
    captions?: CaptionSettings;
    description?: DescriptionSettings;
    /**
     * What a clip shows while it is sitting still: its thumbnail, or the video
     * frame it is parked on. One choice for the whole project, because it is
     * about how the project is reviewed rather than about one clip.
     */
    clip_preview?: ClipPreview;
  };
  files?: {
    original_file?: string;
  };
};

export type SettingsResponse = {
  settings: {
    gemini_api_key?: string;
    youtube_client_secrets?: any;
    codec?: string;
    theme?: 'light' | 'dark';
    video_defaults?: {
      resolution: string;
      aspect_ratio: string;
    };
    // Where a new project's caption settings start. Changing it never touches
    // projects that already exist.
    caption_defaults?: Partial<CaptionSettings>;
    // The text and template every project's descriptions start from. Unlike
    // caption defaults these are read at upload time, so editing them changes
    // what existing projects publish.
    description_defaults?: { text?: string; template?: string };
  };
  pipeline_config: {
    execution_order: string[];
    steps: Record<string, { auto_run: boolean }>;
  };
};

async function apiRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${BASE_URL}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  const response = await fetch(url, { ...options, headers });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.error || `Request failed with status ${response.status}`);
  }

  return response.json();
}

export const createProject = async (
  file: File, 
  resolution: string,
  aspectRatio: string,
  onProgress?: (progress: number) => void
): Promise<{ project_id: string }> => {
  // 1. Init project metadata
  const initResponse = await fetch(`${BASE_URL}/project/init`, {
    method: 'POST',
    body: JSON.stringify({ 
      filename: file.name,
      resolution,
      aspectRatio
    })
  });
  const { project_id } = await initResponse.json();

  // 2. Upload file
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${BASE_URL}/project/upload/${project_id}`);
    
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        const percentComplete = Math.round((event.loaded / event.total) * 100);
        onProgress(percentComplete);
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve({ project_id });
      } else {
        reject(new Error(`Upload failed with status ${xhr.status}`));
      }
    };

    xhr.onerror = () => {
        console.error('XHR Upload Error');
        reject(new Error('Network error during upload'));
    };
    xhr.send(file);
  });
};

export const getStepStatus = async (projectId: string, step: string): Promise<{ status: string }> => {
  return apiRequest(`/project/${projectId}/step_status/${step}`);
};

export const processProject = async (projectId: string) => {
  return apiRequest('/project/process', {
    method: 'POST',
    body: JSON.stringify({ project_id: projectId }),
  });
};

export const getProjects = async (): Promise<ProjectMetadata[]> => {
  return apiRequest('/projects');
};

export const getProjectMetadata = async (projectId: string): Promise<ProjectMetadata> => {
  return apiRequest<ProjectMetadata>(`/project/${projectId}`);
};

// Timeline marker EDL for DaVinci Resolve. `recordStart` must match the
// timecode the Resolve timeline starts at (default 01:00:00:00).
export const getMarkerEdlUrl = (projectId: string, recordStart = '01:00:00:00') => {
  return `${BASE_URL}/project/${projectId}/markers.edl?start=${encodeURIComponent(recordStart)}`;
};

/**
 * The filename the server named the attachment, or null when it did not say.
 *
 * Cross-origin, this header is only readable because the backend lists it in
 * `Access-Control-Expose-Headers`; every caller still needs a fallback name for
 * the case where it is not there.
 */
const filenameFromResponse = (response: Response): string | null => {
  const disposition = response.headers.get('Content-Disposition');
  const match = disposition?.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i);
  return match ? decodeURIComponent(match[1]) : null;
};

/** Hands a fetched body to the browser as a file, then releases it. */
const saveBlob = (blob: Blob, filename: string) => {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  // Revoked on the next frame rather than immediately: Safari has not always
  // finished reading the object URL by the time click() returns.
  requestAnimationFrame(() => URL.revokeObjectURL(url));
};

/**
 * Downloads the marker EDL through fetch rather than by following the link.
 *
 * The plain `<a download>` works only on the happy path. The API is a
 * different origin from the app, so `download` is ignored and the click is a
 * top-level navigation — and on a failure the backend answers with a JSON
 * error, which the browser renders as a page. The export then costs the user
 * the whole app. Fetching it means a failure is an error message on the page
 * that asked for it, and the anchor is still there for middle-click.
 */
export const downloadMarkerEdl = async (
  projectId: string,
  fallbackName: string,
  recordStart?: string
): Promise<void> => {
  const response = await fetch(getMarkerEdlUrl(projectId, recordStart));

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.error || `Export failed with status ${response.status}`);
  }

  saveBlob(await response.blob(), filenameFromResponse(response) ?? `${fallbackName}_markers.edl`);
};

// Chapter exports. `recordStart` must match the timecode the Resolve timeline
// starts at, same rule as the highlight markers above.
export const getChapterEdlUrl = (projectId: string, recordStart = '01:00:00:00') => {
  return `${BASE_URL}/project/${projectId}/chapters.edl?start=${encodeURIComponent(recordStart)}`;
};

export const getChapterTextUrl = (projectId: string) => {
  return `${BASE_URL}/project/${projectId}/chapters.txt`;
};

export type PipelineConfig = {
  execution_order: string[];
  // `llm` marks a step backed by a prompt file; those are collapsed behind a
  // single button in the pipeline controls.
  steps?: Record<string, { auto_run: boolean; llm?: boolean }>;
};

export const getPipelineConfig = async (): Promise<PipelineConfig> => {
  return apiRequest<PipelineConfig>('/pipeline/config');
};

// The values matter, not just the names: the clip preview has to work out the
// exact frame the clipper will render, which needs "9:16" and "1920x1080".
export const getResolutionMap = async (): Promise<Record<string, string>> => {
  return apiRequest<Record<string, string>>('/resolutions');
};

export const getAspectRatioMap = async (): Promise<Record<string, string>> => {
  return apiRequest<Record<string, string>>('/aspect_ratios');
};

export const getResolutions = async (): Promise<string[]> => {
  return Object.keys(await getResolutionMap());
};

export const getAspectRatios = async (): Promise<string[]> => {
  return Object.keys(await getAspectRatioMap());
};

export const getExecutionStatus = async (projectId: string): Promise<Record<string, string>> => {
  return apiRequest(`/project/${projectId}/execution_status`);
};

export const getSourceVideoUrl = (projectId: string, originalFile: string) => {
  return `${BASE_URL}/projects/static/${projectId}/${originalFile.split('/').pop()}`;
};

/**
 * A rendered clip's file.
 *
 * `version` is the highlight's `rendered_at`. A re-cut clip keeps its filename,
 * so without it the browser plays the copy it already has and a regenerated
 * clip looks like nothing happened.
 */
export const getClipVideoUrl = (projectId: string, filename: string, version?: string | null) => {
  const url = `${BASE_URL}/projects/static/${projectId}/clips/${filename}`;
  return version ? `${url}?v=${encodeURIComponent(version)}` : url;
};

/**
 * Where a published clip is edited on YouTube.
 *
 * A Short's "Related video" — the chip that takes a viewer to the full episode
 * — has no field in the Data API and can only be set in Studio, so an upload
 * from here cannot attach it. The link in the description is a different thing.
 * This is the page that does have the control.
 */
/**
 * Whether this clip's published video is still on YouTube.
 *
 * Nothing tells this application when a video it published is deleted, so the
 * record outlives the video: a dead link on the clip page, and a thumbnail
 * button pointed at nothing. Asked when a clip is opened; a video that has gone
 * takes its record with it on the server, so the answer is also the fix.
 *
 * `checked` is false when the question could not be asked — no channel
 * connected, no read scope, no network. That is not a "no", and nothing is
 * cleared on the strength of it.
 */
export type ClipPublication = {
  published: boolean;
  video_id: string | null;
  url: string | null;
  checked: boolean;
};

export const getClipPublication = async (
  projectId: string,
  clipIndex: number
): Promise<ClipPublication> =>
  apiRequest<ClipPublication>(`/project/${projectId}/clip/${clipIndex}/publication`);

export const getStudioEditUrl = (videoId: string) =>
  `https://studio.youtube.com/video/${videoId}/edit`;

export const getSettings = async () => {
  return apiRequest('/settings');
};

export const updateSettings = async (payload: { settings: any, pipeline_config?: any }) => {
  return apiRequest('/settings', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
};

/**
 * The state of the connected YouTube channel.
 *
 * `missing_scopes` is not a broken connection: a token authorised before a
 * scope was added still uploads. It is listed because one of those scopes is
 * what lets the uploader wait for YouTube to finish processing a video before
 * attaching its thumbnail — without it the thumbnail is attached on a guess and
 * can be overwritten by the one YouTube generates.
 */
export type YoutubeStatus = {
  connected: boolean;
  reason?: string;
  expired?: boolean;
  has_refresh_token?: boolean;
  account?: string | null;
  missing_scopes?: string[];
  has_client_secrets: boolean;
  consent?: { pending: boolean; completed: boolean; cancelled: boolean; error: string | null };
};

export const getYoutubeStatus = async (): Promise<YoutubeStatus> => {
  return apiRequest('/youtube/status');
};

/**
 * Starts a consent and returns the Google URL to open.
 *
 * The backend does not open it: for a backend in a container the browser that
 * has to do the consenting is not on the same machine as the process.
 *
 * A consent already waiting is ended to make room for this one, so this is
 * also how a user retries after closing the tab on the last attempt.
 */
export const connectYoutube = async (): Promise<{ authorization_url: string }> => {
  return apiRequest('/youtube/connect', { method: 'POST' });
};

/** Abandons a consent left waiting in a browser. */
export const cancelYoutubeConnect = async (): Promise<{ status: string }> => {
  return apiRequest('/youtube/connect/cancel', { method: 'POST' });
};

export const updateCodec = async (codec: string) => {
  return apiRequest('/settings/codec', {
    method: 'POST',
    body: JSON.stringify({ codec }),
  });
};

export const getActiveProcesses = async (): Promise<string[]> => {
  return apiRequest('/active_processes');
};

export const executePipelineStep = async (projectId: string, step: string, action: 'START' | 'STOP') => {
  return apiRequest('/project/step', {
    method: 'POST',
    body: JSON.stringify({ project_id: projectId, step, action }),
  });
};

/**
 * Cuts one clip afresh and publishes it.
 *
 * The clip is always re-rendered first, so what goes up is the clip as the page
 * shows it rather than whatever was cut before the last change to its captions
 * or title. That makes this an encode, which outlives a browser request, so it
 * resolves when the job has been registered — not when the video is live. Watch
 * the key it returns on `/active_processes`, then read the highlight for
 * `youtube_url` or `upload_error`.
 */
export const uploadClip = async (
  projectId: string,
  clipIndex: number
): Promise<{ status: string; job: string }> => {
  return apiRequest(`/project/${projectId}/clip/${clipIndex}/upload`, {
    method: 'POST',
  });
};

/**
 * Puts a published clip's current thumbnail on its video.
 *
 * Not another upload: the video keeps its id, its views and its comments, and
 * only the still changes. For a clip whose picture was changed after it went
 * up — or was published before the uploader sent the rendered file at all.
 */
export const uploadClipThumbnail = async (
  projectId: string,
  clipIndex: number
): Promise<{ status: string; thumbnail_set: boolean; video_id: string; url: string | null }> => {
  return apiRequest(`/project/${projectId}/clip/${clipIndex}/thumbnail/upload`, {
    method: 'POST',
  });
};

export const getCaptionStyles = async (): Promise<Record<string, CaptionStyle>> => {
  return apiRequest<Record<string, CaptionStyle>>('/caption_styles');
};

// Cues and style for one highlight. The same two things the burned render uses,
// so the overlay drawn over the preview is what the clipper will produce.
export const getClipCaptions = async (projectId: string, clipIndex: number): Promise<CaptionPreview> => {
  return apiRequest<CaptionPreview>(`/project/${projectId}/clip/${clipIndex}/captions`);
};

// The font file itself, served by the API so the page draws with the same one
// libass will.
export const getCaptionFontUrl = (path: string) => `${BASE_URL}${path}`;

// The same captions as a subtitle file, sized for the frame it will sit on.
export const getClipCaptionsAssUrl = (projectId: string, clipIndex: number, width = 1080, height = 1920) => {
  return `${BASE_URL}/project/${projectId}/clip/${clipIndex}/captions.ass?width=${width}&height=${height}`;
};

// The description one clip would be uploaded with, rendered by the backend so
// the preview and the upload cannot say different things.
export const getClipDescription = async (
  projectId: string,
  clipIndex: number
): Promise<{ description: string; template: string }> => {
  return apiRequest(`/project/${projectId}/clip/${clipIndex}/description`);
};

// The placeholders a description template may use, and the template the app
// ships with.
export const getDescriptionFields = async (): Promise<{
  fields: DescriptionField[];
  default_template: string;
}> => {
  return apiRequest('/description_fields');
};

export const updateProjectSettings = async (
  projectId: string,
  settings: {
    resolution?: string;
    aspect_ratio?: string;
    captions?: Partial<CaptionSettings>;
    description?: Partial<DescriptionSettings>;
    clip_preview?: ClipPreview;
  }
) => {
  return apiRequest(`/project/${projectId}/settings`, {
    method: 'PUT',
    body: JSON.stringify(settings),
  });
};

/**
 * One clip's caption settings, or `null` to put it back under the project's.
 *
 * The whole object is sent rather than a patch: a clip is either locked or
 * speaking for itself, and a partial update says nothing about which.
 */
export const updateClipCaptions = async (
  projectId: string,
  clipIndex: number,
  captions: CaptionSettings | null
) => {
  return apiRequest(`/project/${projectId}/clip/${clipIndex}/captions`, {
    method: 'PUT',
    body: JSON.stringify({ captions }),
  });
};

/**
 * One clip's title, or `null` to take it off the clip entirely.
 *
 * The whole object is sent rather than a patch, for the same reason the caption
 * settings are: the editor holds the whole form. What comes back is the stored
 * value after the backend has clamped it, which is what will actually be burned.
 */
export const updateClipOverlay = async (
  projectId: string,
  clipIndex: number,
  overlay: OverlayText | null
): Promise<{ status: string; overlay: OverlayText | null }> => {
  return apiRequest(`/project/${projectId}/clip/${clipIndex}/overlay`, {
    method: 'PUT',
    body: JSON.stringify({ overlay }),
  });
};

/**
 * One clip's thumbnail: how it is built, what text it will carry, whether the
 * image has been rendered yet.
 */
export const getClipThumbnail = async (
  projectId: string,
  clipIndex: number
): Promise<ThumbnailPreview> => {
  return apiRequest<ThumbnailPreview>(`/project/${projectId}/clip/${clipIndex}/thumbnail`);
};

/**
 * Saves how one clip's thumbnail should be built, or `null` for the defaults.
 *
 * Saving describes the *next* render: the image on disk is not touched until
 * `generateClipThumbnail` is called, which is why the two are separate.
 */
export const updateClipThumbnail = async (
  projectId: string,
  clipIndex: number,
  thumbnail: ThumbnailSettings | null
): Promise<{ status: string; thumbnail: ThumbnailSettings | null }> => {
  return apiRequest(`/project/${projectId}/clip/${clipIndex}/thumbnail`, {
    method: 'PUT',
    body: JSON.stringify({ thumbnail }),
  });
};

/**
 * Renders the thumbnail now.
 *
 * Unlike a clip re-cut this resolves when the picture exists: it is one frame,
 * and the picture is the thing the user is waiting to look at.
 */
export const generateClipThumbnail = async (
  projectId: string,
  clipIndex: number
): Promise<{ status: string; thumbnail: ThumbnailSettings }> => {
  return apiRequest(`/project/${projectId}/clip/${clipIndex}/thumbnail`, {
    method: 'POST',
  });
};

/**
 * A rendered thumbnail's image.
 *
 * `version` is the settings' `generated_at`. Like a re-cut clip, a re-made
 * thumbnail keeps its filename, so without it the browser shows the copy it
 * already has.
 */
export const getClipThumbnailUrl = (
  projectId: string,
  filename: string,
  version?: string | null
) => {
  const url = `${BASE_URL}/projects/static/${projectId}/thumbnails/${filename}`;
  return version ? `${url}?v=${encodeURIComponent(version)}` : url;
};

/**
 * Re-cuts one clip with whatever its settings now say.
 *
 * Unlike `uploadClip` this returns as soon as the render has been queued — an
 * encode outlives a browser request. The `job` it answers with is a key on
 * `/active_processes`, which is gone once the new file is on disk.
 */
export const regenerateClip = async (
  projectId: string,
  clipIndex: number
): Promise<{ status: string; job: string }> => {
  return apiRequest(`/project/${projectId}/clip/${clipIndex}/regenerate`, {
    method: 'POST',
  });
};

export const deleteClip = async (projectId: string, clipIndex: number) => {
  const response = await fetch(`${BASE_URL}/project/${projectId}/clip/${clipIndex}`, { method: 'DELETE' });
  if (!response.ok) throw new Error('Failed to delete clip');
  return { status: 'deleted' };
};

export const deleteProject = async (projectId: string) => {
  // fetch delete doesn't return data usually, but this satisfies the existing signature
  const response = await fetch(`${BASE_URL}/project/${projectId}`, { method: 'DELETE' });
  if (!response.ok) throw new Error('Failed to delete project');
  return { status: 'deleted' };
};
