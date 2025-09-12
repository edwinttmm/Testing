import React from 'react';
import LabJackErrorBoundary from './LabJackErrorBoundary';
import LabJackStatusPanel from './LabJackStatusPanel';

interface SafeLabJackStatusPanelProps {
  onDataReceived?: (data: {
    data: number[];
    timestamp: number;
    sample_rate: number;
    channels: string[];
  }) => void;
  onStatusChanged?: (status: any) => void;
}

/**
 * A safe wrapper around LabJackStatusPanel that provides error boundary protection
 * and graceful fallback when the LabJack component encounters errors
 */
const SafeLabJackStatusPanel: React.FC<SafeLabJackStatusPanelProps> = (props) => {
  return (
    <LabJackErrorBoundary>
      <LabJackStatusPanel {...props} />
    </LabJackErrorBoundary>
  );
};

export default SafeLabJackStatusPanel;