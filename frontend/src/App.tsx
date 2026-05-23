import { useState, useEffect } from 'react';
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { createProject, getProjects, getProjectMetadata, executePipelineStep, getPipelineConfig, getActiveProcesses, deleteProject } from './api';
import { ProjectDetail } from './components/ProjectDetail/ProjectDetail';
import { ClipDetail } from './components/ClipManagement/ClipDetail';
import { ProjectHistory } from './components/History/ProjectHistory';
import { FileUploader } from './components/FileUploader';
import { Header } from './components/Header';
import { Navigation } from './components/Navigation';
import { Breadcrumbs } from './components/Breadcrumbs';
import { ConfirmationModal } from './components/ConfirmationModal';
import { ThemeToggle } from './components/ThemeToggle';
import { SettingsPage } from './components/SettingsPage';
import './index.css';

// Cookie Helpers
const getCookie = (name: string): string | null => {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop()?.split(';').shift() || null;
  return null;
};

const setCookie = (name: string, value: string, days: number = 365) => {
  const date = new Date();
  date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
  document.cookie = `${name}=${value};expires=${date.toUTCString()};path=/`;
};

export default function App() {
  const navigate = useNavigate();
  const location = useLocation();
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    const savedTheme = getCookie('app-theme');
    return (savedTheme === 'dark' || savedTheme === 'light') ? savedTheme : 'light';
  });
  
  const [file, setFile] = useState<File | null>(null);
  const queryClient = useQueryClient();
  const [confirmDeleteProject, setConfirmDeleteProject] = useState({
    isOpen: false,
    projectId: '',
    projectName: '',
  });

  useEffect(() => {
    setCookie('app-theme', theme);
  }, [theme]);

  // Helper to extract project ID and clip index from URL
  const projectIdMatch = location.pathname.match(/^\/project\/([a-zA-Z0-9-]+)/);
  const projectId = projectIdMatch ? projectIdMatch[1] : null;
  const clipMatch = location.pathname.match(/\/clip\/(\d+)/);
  const clipIndex = clipMatch ? clipMatch[1] : null;

  const { data: projects = [], refetch: refetchProjects } = useQuery({ 
    queryKey: ['projects'], 
    queryFn: getProjects
  });

  const { data: activeProcesses = [], refetch: refetchProcesses } = useQuery({
    queryKey: ['activeProcesses'],
    queryFn: getActiveProcesses,
    refetchInterval: (query) => (query.state.data && query.state.data.length > 0 ? 1000 : false),
    refetchOnWindowFocus: false,
  });

  const { data: pipelineConfig } = useQuery({
    queryKey: ['pipelineConfig'],
    queryFn: getPipelineConfig,
  });

  const { data: projectMetadata } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => getProjectMetadata(projectId!),
    enabled: !!projectId,
    refetchInterval: () => {
      const isActive = activeProcesses.some(processId => processId.startsWith(`${projectId}_`));
      return isActive ? 1000 : false;
    },
    refetchOnWindowFocus: false,
  });

  const createMutation = useMutation({
    mutationFn: createProject,
    onSuccess: (data) => {
      navigate(`/project/${data.project_id}`);
    },
    onError: (error: any) => console.error(error)
  });

  const deleteProjectMutation = useMutation({
    mutationFn: deleteProject,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      setConfirmDeleteProject({ isOpen: false, projectId: '', projectName: '' });
      navigate('/history');
    },
    onError: (error: any) => {
      console.error(error);
      setConfirmDeleteProject({ isOpen: false, projectId: '', projectName: '' });
    }
  });

  const stepMutation = useMutation({
    mutationFn: ({ action, step }: { action: 'START' | 'STOP', step: string }) => 
      executePipelineStep(projectId!, step, action),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project', projectId] });
      refetchProcesses();
    }
  });

  const handleSubmit = () => {
    if (file) {
      createMutation.mutate(file);
    }
  };

  const isHome = location.pathname === '/';

  // Generate Breadcrumbs
  const breadcrumbs = [];
  breadcrumbs.push({ label: 'HOME', onClick: () => navigate('/') });

  if (location.pathname !== '/') {
    breadcrumbs.push({ label: 'PROJECTS', onClick: () => navigate('/history') });
  }

  if (projectId) {
    breadcrumbs.push({ 
      label: projectMetadata?.name || 'Loading...', 
      onClick: () => navigate(`/project/${projectId}`) 
    });
  }

  if (clipIndex) {
    breadcrumbs.push({ 
      label: `CLIP ${parseInt(clipIndex) + 1}`, 
      onClick: () => {} 
    });
  }

  return (
    <div 
      data-theme={theme}
      style={{ 
        padding: 'var(--space-md)', 
        display: 'flex', 
        flexDirection: 'column',
        minHeight: '100vh',
        background: 'var(--bg)',
        color: 'var(--text)'
      }}
    >
      <div style={{ 
        display: 'flex', 
        flexDirection: 'column', 
        width: '100%'
      }}>
        <div style={{ 
          display: 'flex', 
          flexDirection: 'column',
          width: '100%',
          marginBottom: 'var(--space-sm)',
        }}>
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center',
            width: '100%',
            borderBottom: 'var(--border)',
            paddingBottom: 'var(--space-sm)'
          }}>
            <Header />
            <Navigation 
              onHistoryClick={() => { refetchProjects(); navigate('/history'); }} 
            />
          </div>
          <Breadcrumbs items={breadcrumbs} />
        </div>

        <div style={{ 
          width: '100%', 
          display: 'flex',
          flexDirection: 'column',
          alignItems: isHome ? 'center' : 'flex-start',
          textAlign: isHome ? 'center' : 'left'
        }}>
          <Routes>
            <Route path="/" element={
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)', width: '100%' }}>
                {createMutation.isError && (
                  <div style={{ 
                    border: '4px solid var(--error)', 
                    padding: 'var(--space-md)', 
                    backgroundColor: 'var(--bg)', 
                    color: 'var(--error)',
                    fontWeight: 900,
                    textTransform: 'uppercase',
                    boxShadow: '4px 4px 0px var(--error)',
                    textAlign: 'center',
                    animation: 'entrance 400ms var(--ease-out-quart)'
                  }}>
                    CRITICAL ERROR: {createMutation.error instanceof Error ? createMutation.error.message : 'Failed to create project'}
                  </div>
                )}
                <FileUploader 
                  onFileSelect={(f) => setFile(f)} 
                  isPending={createMutation.isPending} 
                  onSubmit={handleSubmit} 
                />
              </div>
            } />
            <Route path="/project/:id" element={
              <div style={{ width: '100%' }}>
                {projectMetadata ? (
                  <ProjectDetail 
                    metadata={projectMetadata} 
                    pipelineConfig={pipelineConfig || { execution_order: [] }}
                    activeProcesses={activeProcesses}
                    onExecuteAction={(action, step) => stepMutation.mutate({ action, step: step === 'all' ? 'all' : step })} 
                    onDeleteClip={(index) => console.log('Deleting clip:', index)}
                    onDeleteProject={() => setConfirmDeleteProject({ 
                      isOpen: true, 
                      projectId: projectId!, 
                      projectName: projectMetadata.name 
                    })}
                  />
                ) : <p>Loading...</p>}
              </div>
            } />
            <Route path="/project/:id/clip/:clipIndex" element={<ClipDetail />} />
            <Route path="/history" element={
              <ProjectHistory projects={projects} />
            } />
            <Route path="/settings" element={
              <SettingsPage theme={theme} setTheme={setTheme} />
            } />
          </Routes>
        </div>
      </div>

      <ConfirmationModal 
        isOpen={confirmDeleteProject.isOpen}
        title="Delete Project"
        message={`Are you sure you want to delete project "${confirmDeleteProject.projectName}"? This action cannot be undone.`}
        onConfirm={() => deleteProjectMutation.mutate(confirmDeleteProject.projectId)}
        onCancel={() => setConfirmDeleteProject({ isOpen: false, projectId: '', projectName: '' })}
      />
      <ThemeToggle theme={theme} setTheme={setTheme} />
    </div>
  );
}
