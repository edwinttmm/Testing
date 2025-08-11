import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import Header from '../Layout/Header';

// Mock react-router-dom
jest.mock('react-router-dom', () => ({
  useNavigate: () => jest.fn(),
}));

describe('Header Component', () => {
  test('renders header with title', () => {
    render(<Header />);
    
    expect(screen.getByText('AI Model Validation Platform')).toBeInTheDocument();
  });

  test('renders notification icon', () => {
    render(<Header />);
    
    const notificationButton = screen.getByRole('button', { name: /notifications/i });
    expect(notificationButton).toBeInTheDocument();
  });

  test('renders user avatar', () => {
    render(<Header />);
    
    const avatarButton = screen.getByRole('button');
    expect(avatarButton).toBeInTheDocument();
  });

  test('opens user menu when avatar is clicked', () => {
    render(<Header />);
    
    const avatarButton = screen.getByLabelText(/account of current user/i);
    fireEvent.click(avatarButton);
    
    expect(screen.getByText('Demo User')).toBeInTheDocument();
    expect(screen.getByText('demo@example.com')).toBeInTheDocument();
  });

  test('displays profile menu item', () => {
    render(<Header />);
    
    const avatarButton = screen.getByLabelText(/account of current user/i);
    fireEvent.click(avatarButton);
    
    expect(screen.getByText('Profile & Settings')).toBeInTheDocument();
  });

  test('notification badge displays count', () => {
    render(<Header />);
    
    const badge = screen.getByText('4');
    expect(badge).toBeInTheDocument();
  });
});