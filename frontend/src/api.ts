const BASE_URL = 'http://localhost:8000';

export type ProjectMetadata = {
  project_id: string;
  name: string;
  created_at: string;
  clips: any[];
  clips_count?: number;
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
  onProgress?: (progress: number) => void
): Promise<{ project_id: string }> => {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${BASE_URL}/project/create`);
    xhr.setRequestHeader('Content-Type', 'application/octet-stream');
    xhr.setRequestHeader('X-File-Name', file.name);

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        // Cap upload progress at 95% to leave room for server-side processing/finalization
        const percentComplete = Math.min(95, Math.round((event.loaded / event.total) * 100));
        onProgress(percentComplete);
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        if (onProgress) onProgress(100);
        resolve(JSON.parse(xhr.responseText));
      } else {
        const errorData = JSON.parse(xhr.responseText || '{}');
        reject(new Error(errorData.error || `Upload failed with status ${xhr.status}`));
      }
    };

    xhr.onerror = () => reject(new Error('Network error during upload'));
    xhr.send(file);
  });
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

export const deleteProject = async (projectId: string) => {
  // fetch delete doesn't return data usually, but this satisfies the existing signature
  const response = await fetch(`${BASE_URL}/project/${projectId}`, { method: 'DELETE' });
  if (!response.ok) throw new Error('Failed to delete project');
  return { status: 'deleted' };
};
