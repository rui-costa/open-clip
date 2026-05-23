import axios from 'axios';

export type ProjectMetadata = {
  project_id: string;
  name: string;
  created_at: string;
  clips: any[];
  clips_count?: number;
};

const api = axios.create({
  baseURL: 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
});

export const createProject = async (file: File) => {
  const response = await api.post('/project/create', file, {
    headers: {
      'Content-Type': 'application/octet-stream',
      'X-File-Name': file.name,
    },
  });
  return response.data;
};

export const processProject = async (projectId: string) => {
  const response = await api.post('/project/process', { project_id: projectId });
  return response.data;
};

export const getProjects = async (): Promise<ProjectMetadata[]> => {
  const response = await api.get('/projects');
  return response.data;
};

export const getProjectMetadata = async (projectId: string) => {
  const response = await api.get(`/project/${projectId}`);
  return response.data;
};

export const getPipelineConfig = async () => {
  const response = await api.get('/pipeline/config');
  return response.data;
};

export const getSettings = async () => {
  const response = await api.get('/settings');
  return response.data;
};

export const updateSettings = async (payload: { settings: any, pipeline_config?: any }) => {
  const response = await api.post('/settings', payload);
  return response.data;
};

export const getActiveProcesses = async (): Promise<string[]> => {
  const response = await api.get('/active_processes');
  return response.data;
};

export const executePipelineStep = async (projectId: string, step: string, action: 'START' | 'STOP') => {
  const response = await api.post('/project/step', { project_id: projectId, step, action });
  return response.data;
};

export const uploadClip = async (projectId: string, clipIndex: number) => {
  const response = await api.post(`/project/${projectId}/clip/${clipIndex}/upload`);
  return response.data;
};

export const deleteProject = async (projectId: string) => {
  const response = await api.delete(`/project/${projectId}`);
  return response.data;
};
