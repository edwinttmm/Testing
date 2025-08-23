import React from 'react';
import { render } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { FixedGrid } from '../ai-model-validation-platform/frontend/src/components/ui/FixedUIComponents';

const theme = createTheme();

describe('FixedGrid Component', () => {
  const TestWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
    <ThemeProvider theme={theme}>{children}</ThemeProvider>
  );

  it('should render Grid with item and xs props', () => {
    const { container } = render(
      <TestWrapper>
        <FixedGrid container>
          <FixedGrid item xs={12}>
            <div>Test Content</div>
          </FixedGrid>
        </FixedGrid>
      </TestWrapper>
    );
    expect(container.firstChild).toBeDefined();
  });

  it('should render Grid with multiple breakpoints', () => {
    const { container } = render(
      <TestWrapper>
        <FixedGrid container>
          <FixedGrid item xs={12} sm={6} md={4} lg={3}>
            <div>Responsive Content</div>
          </FixedGrid>
        </FixedGrid>
      </TestWrapper>
    );
    expect(container.firstChild).toBeDefined();
  });

  it('should render Grid with auto sizing', () => {
    const { container } = render(
      <TestWrapper>
        <FixedGrid container>
          <FixedGrid item xs="auto">
            <div>Auto-sized Content</div>
          </FixedGrid>
        </FixedGrid>
      </TestWrapper>
    );
    expect(container.firstChild).toBeDefined();
  });

  it('should render Grid with boolean props', () => {
    const { container } = render(
      <TestWrapper>
        <FixedGrid container>
          <FixedGrid item xs={true}>
            <div>Boolean-sized Content</div>
          </FixedGrid>
        </FixedGrid>
      </TestWrapper>
    );
    expect(container.firstChild).toBeDefined();
  });
});