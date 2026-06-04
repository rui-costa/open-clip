import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import type { ProjectMetadata } from '../../api';
import { deleteProject } from '../../api';
import { ConfirmationModal } from '../ConfirmationModal';
import { Button } from '../Button';

interface ProjectHistoryProps {
  projects: ProjectMetadata[];
}

export const ProjectHistory: React.FC<ProjectHistoryProps> = ({ projects }) => {
  const navigate = useNavigate();
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
        <h2>All Projects</h2>
        <p style={{ 
          color: 'var(--text)', 
          fontWeight: 'bold', 
          textTransform: 'uppercase', 
          fontSize: '1rem',
          marginBottom: 'var(--space-md)' 
        }}>
          Manage and revisit your projects.
        </p>
      </header>

      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(auto-fill, 300px)', 
        gap: 'var(--space-md)',
        justifyContent: 'center'
      }}>
        {projects.length > 0 ? (
          projects.map((project, index) => (
            <div 
              key={project.project_id} 
              onClick={() => navigate(`/project/${project.project_id}`)}
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
                <span style={{ 
                  fontSize: '1.5rem', 
                  fontWeight: '900', 
                  textTransform: 'uppercase', 
                  lineHeight: '1.1',
                  display: 'block',
                  marginBottom: 'var(--space-sm)'
                }}>
                  {project.name}
                </span>
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
            border: 'var(--border)',
            fontWeight: '900', 
            textTransform: 'uppercase',
            fontSize: '2rem'
          }}>
            No projects found.
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
