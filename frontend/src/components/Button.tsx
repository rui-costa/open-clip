import React from 'react';

export type ButtonVariant = 'primary' | 'danger' | 'ghost';
export type ButtonSize = 'sm' | 'md' | 'lg';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  children: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({ 
  variant = 'primary', 
  size = 'md',
  children, 
  style, 
  className,
  ...props 
}) => {
  const variantClass = {
    primary: 'btn-primary',
    danger: 'btn-danger',
    ghost: 'btn-ghost',
  }[variant];

  const sizeClass = {
    sm: 'btn-sm',
    md: 'btn-md',
    lg: 'btn-lg',
  }[size];

  return (
    <button 
      {...props} 
      className={`${variantClass} ${sizeClass} ${className || ''}`}
      style={{ ...style }}
    >
      {children}
    </button>
  );
};
