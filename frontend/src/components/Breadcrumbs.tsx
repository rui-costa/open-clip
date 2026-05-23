import React from 'react';

interface BreadcrumbItem {
  label: string;
  onClick: () => void;
}

interface BreadcrumbsProps {
  items: BreadcrumbItem[];
}

export const Breadcrumbs: React.FC<BreadcrumbsProps> = ({ items }) => {
  return (
    <nav aria-label="Breadcrumb" style={{ marginBottom: 'var(--space-md)', fontSize: '0.9rem', color: 'var(--text-muted)' }}>
      <ol style={{ listStyle: 'none', display: 'flex', gap: 'var(--space-xs)', padding: 0, margin: 0 }}>
        {items.map((item, index) => (
          <li key={index} style={{ display: 'flex', alignItems: 'center' }}>
            {index > 0 && <span style={{ marginRight: 'var(--space-xs)' }}>/</span>}
            <button
              onClick={item.onClick}
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                padding: 0,
                color: index === items.length - 1 ? 'var(--accent)' : 'inherit',
                textDecoration: index === items.length - 1 ? 'none' : 'underline',
              }}
            >
              {item.label}
            </button>
          </li>
        ))}
      </ol>
    </nav>
  );
};
