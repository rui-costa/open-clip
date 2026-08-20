import React from 'react';

interface BreadcrumbItem {
  label: string;
  // The trailing crumb is the current page, so it has nowhere to navigate to.
  onClick?: () => void;
}

interface BreadcrumbsProps {
  items: BreadcrumbItem[];
}

export const Breadcrumbs: React.FC<BreadcrumbsProps> = ({ items }) => {
  return (
    <nav aria-label="Breadcrumb" style={{ marginBottom: 'var(--space-md)', fontSize: '0.9rem', color: 'var(--text-muted)' }}>
      <ol style={{ listStyle: 'none', display: 'flex', flexWrap: 'wrap', gap: 'var(--space-xs)', padding: 0, margin: 0 }}>
        {items.map((item, index) => {
          const isCurrent = index === items.length - 1;
          return (
            <li key={index} style={{ display: 'flex', alignItems: 'center' }}>
              {index > 0 && <span aria-hidden="true" style={{ marginRight: 'var(--space-xs)' }}>/</span>}
              {isCurrent || !item.onClick ? (
                <span aria-current="page" style={{ color: 'var(--text-accent)', fontWeight: 700 }}>
                  {item.label}
                </span>
              ) : (
                <button
                  onClick={item.onClick}
                  style={{
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    padding: 0,
                    font: 'inherit',
                    textTransform: 'none',
                    color: 'inherit',
                    textDecoration: 'underline',
                  }}
                >
                  {item.label}
                </button>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
};
