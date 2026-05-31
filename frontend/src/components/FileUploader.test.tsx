import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { FileUploader } from './FileUploader';

describe('FileUploader Component', () => {
  it('renders the upload instructions correctly when no file is selected', () => {
    render(
      <FileUploader 
        onFileSelect={vi.fn()} 
        isPending={false} 
        uploadProgress={0}
        onSubmit={vi.fn()} 
      />
    );
    
    expect(screen.getByText(/Upload Video/i)).toBeDefined();
    expect(screen.getByText(/Drag and drop your video file here/i)).toBeDefined();
  });

  it('renders the "DROP VIDEO HERE" indicator', () => {
    render(
      <FileUploader 
        onFileSelect={vi.fn()} 
        isPending={false} 
        uploadProgress={0}
        onSubmit={vi.fn()} 
      />
    );
    
    expect(screen.getByText(/DROP VIDEO HERE/i)).toBeDefined();
  });
});
