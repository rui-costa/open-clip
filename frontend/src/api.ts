const BASE_URL = 'http://localhost:8000';

export type ProjectMetadata = {
  project_id: string;
  name: string;
  created_at: string;
  clips: any[];
  highlights: any[];
  clips_count?: number;
  step_statuses?: Record<string, string>;
};

export type SettingsResponse = {
  settings: {
    gemini_api_key?: string;
    youtube_client_secrets?: any;
    theme?: 'light' | 'dark';
    video_defaults?: {
      resolution: string;
      aspect_ratio: string;
    };
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
  console.log('Project initialized, starting upload to:', `${BASE_URL}/project/upload/${project_id}`);

  // 2. Upload file
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${BASE_URL}/project/upload/${project_id}`);
    
    xhr.upload.onprogress = (event) => {
      console.log('Upload progress:', event.loaded, '/', event.total);
      if (event.lengthComputable && onProgress) {
        const percentComplete = Math.round((event.loaded / event.total) * 100);
        onProgress(percentComplete);
      }
    };

    xhr.onload = () => {
      console.log('Upload finished, status:', xhr.status);
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

export const getProjectMetadata = async (projectId: string) => {
  return apiRequest(`/project/${projectId}`);
};

export const getPipelineConfig = async () => {
  return apiRequest('/pipeline/config');
};

export const getSettings = async () => {
  return apiRequest('/settings');
};

export const updateSettings = async (payload: { settings: any, pipeline_config?: any }) => {
  return apiRequest('/settings', {
    method: 'POST',
    body: JSON.stringify(payload),
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

export const uploadClip = async (projectId: string, clipIndex: number) => {
  return apiRequest(`/project/${projectId}/clip/${clipIndex}/upload`, {
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
