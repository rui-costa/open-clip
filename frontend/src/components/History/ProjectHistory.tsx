import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import type { ProjectMetadata } from '../../api';
import { deleteProject } from '../../api';
import { ConfirmationModal } from '../ConfirmationModal';
import { Button } from '../Button';

interface ProjectHistoryProps {
  projects: ProjectMetadata[];
}

export const ProjectHistory: React.FC<ProjectHistoryProps> = ({ projects }) => {
  const queryClient = useQueryClient();
  const [confirmDelete, setConfirmDelete] = useState<{ isOpen: boolean; projectId: string; projectName: string }>({
    isOpen: false,
    projectId: '',
    projectName: '',
  });

  const deleteMutation = useMutation({
    mutationFn: (projectId: string) => deleteProject(projectId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      setConfirmDelete({ isOpen: false, projectId: '', projectName: '' });
    },
  });

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { 
      month: 'short', 
      day: 'numeric', 
      year: 'numeric' 
    });
  };

  return (
    <div className="project-history" style={{ margin: '0 auto', width: '100%' }}>
      <header style={{ marginBottom: 'var(--space-xl)', textAlign: 'center' }}>
        <h1 style={{ fontSize: 'clamp(2rem, 5vw, 3rem)' }}>All Projects</h1>
      </header>

      <div className="card-grid">
        {projects.length > 0 ? (
          projects.map((project, index) => (
            <div
              key={project.project_id}
              style={{
                position: 'relative',
                padding: 'var(--space-md)', 
                border: 'var(--border)', 
                borderRadius: '0',
                cursor: 'pointer',
                transition: 'all 200ms var(--ease-out-quart)',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                aspectRatio: '16 / 9',
                animation: `entrance 600ms var(--ease-out-quart) ${index * 100}ms backwards`,
                backgroundColor: 'var(--bg)',
                color: 'var(--text)',
                textAlign: 'left',
                width: '100%'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = 'var(--text)';
                e.currentTarget.style.color = 'var(--bg)';
                e.currentTarget.style.transform = 'translate(-4px, -4px)';
                e.currentTarget.style.boxShadow = '4px 4px 0px var(--accent)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'var(--bg)';
                e.currentTarget.style.color = 'var(--text)';
                e.currentTarget.style.transform = 'translate(0, 0)';
                e.currentTarget.style.boxShadow = 'none';
              }}
            >
              <div>
                <Link
                  to={`/project/${project.project_id}`}
                  style={{
                    fontSize: '1.5rem',
                    fontWeight: '900',
                    textTransform: 'uppercase',
                    lineHeight: '1.1',
                    display: 'block',
                    marginBottom: 'var(--space-sm)',
                    color: 'inherit',
                    textDecoration: 'none'
                  }}
                >
                  {project.name}
                  {/* Stretches the link over the whole card so the card stays
                      clickable without nesting the Delete button inside it. */}
                  <span style={{ position: 'absolute', inset: 0, zIndex: 1 }} />
                </Link>
                <div style={{ 
                  display: 'flex', 
                  flexDirection: 'column', 
                  gap: '4px',
                  fontSize: '0.8rem',
                  fontWeight: '900',
                  textTransform: 'uppercase',
                  opacity: 0.8
                }}>
                  <span>DATE: {formatDate(project.created_at)}</span>
                  <span>CLIPS: {project.highlights?.filter((h: any) => h.is_clip_generated).length ?? 0}</span>
                </div>
              </div>
              <div style={{ 
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                fontSize: '0.9rem', 
                fontWeight: '900', 
                textTransform: 'uppercase',
                marginTop: 'var(--space-md)',
              }}>
                <span style={{ 
                  display: 'flex',
                  alignItems: 'center',
                  gap: 'var(--space-sm)',
                  color: 'var(--accent)'
                }}
                onMouseEnter={(e) => e.currentTarget.style.color = 'var(--bg)'}
                onMouseLeave={(e) => e.currentTarget.style.color = 'var(--accent)'}
                >
                  View Project <span style={{ fontSize: '1.2rem' }}>→</span>
                </span>
                <Button 
                  variant="danger"
                  onClick={(e) => {
                    e.stopPropagation();
                    setConfirmDelete({ 
                      isOpen: true, 
                      projectId: project.project_id, 
                      projectName: project.name 
                    });
                  }}
                  style={{
                    fontSize: '0.7rem',
                    padding: '0.25rem 0.5rem',
                    position: 'relative',
                    zIndex: 2,
                  }}
                >
                  DELETE
                </Button>
              </div>
            </div>
          ))
        ) : (
          <div style={{
            gridColumn: '1 / -1',
            padding: 'var(--space-xl)',
            textAlign: 'center',
            border: '4px dashed var(--text)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 'var(--space-md)'
          }}>
            <h2 style={{ margin: 0, fontSize: '2rem', fontWeight: 900, textTransform: 'uppercase' }}>
              No projects yet
            </h2>
            {/* The only place a project can be created is the home route, and
                nothing here previously pointed at it. */}
            <p style={{ margin: 0, maxWidth: '420px', lineHeight: 1.4 }}>
              Upload a video and Open-Clip will transcribe it, find the highlights, and cut them into clips.
            </p>
            <Link
              to="/"
              className="btn-primary btn-md"
              style={{ textDecoration: 'none', display: 'inline-block' }}
            >
              Upload a video
            </Link>
          </div>
        )}
      </div>

      <ConfirmationModal 
        isOpen={confirmDelete.isOpen}
        title="Delete Project"
        message={`Are you sure you want to delete project "${confirmDelete.projectName}"? This action cannot be undone.`}
        onConfirm={() => deleteMutation.mutate(confirmDelete.projectId)}
        onCancel={() => setConfirmDelete({ isOpen: false, projectId: '', projectName: '' })}
      />
    </div>
  );
};
