import React from 'react';
import ReactDOM from 'react-dom/client';
import BoundaryBoxDemo from './pages/BoundaryBoxDemo';

const root = ReactDOM.createRoot(
  document.getElementById('root') as HTMLElement
);

root.render(
  <React.StrictMode>
    <BoundaryBoxDemo />
  </React.StrictMode>
);