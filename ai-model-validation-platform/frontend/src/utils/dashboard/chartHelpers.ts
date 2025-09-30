/**
 * Chart configuration generators and color schemes for dashboard visualizations
 */

import { ChartOptions, TooltipItem, ChartData } from 'chart.js';

export interface ChartColorScheme {
  primary: string;
  secondary: string;
  success: string;
  warning: string;
  danger: string;
  info: string;
  light: string;
  dark: string;
}

export interface GradientColors {
  start: string;
  end: string;
}

/**
 * Default color schemes for different chart types
 */
export const colorSchemes: Record<string, ChartColorScheme> = {
  default: {
    primary: '#3B82F6',
    secondary: '#6B7280',
    success: '#10B981',
    warning: '#F59E0B',
    danger: '#EF4444',
    info: '#06B6D4',
    light: '#F3F4F6',
    dark: '#1F2937',
  },
  dark: {
    primary: '#60A5FA',
    secondary: '#9CA3AF',
    success: '#34D399',
    warning: '#FBBF24',
    danger: '#F87171',
    info: '#22D3EE',
    light: '#374151',
    dark: '#111827',
  },
  colorful: {
    primary: '#8B5CF6',
    secondary: '#EC4899',
    success: '#06D6A0',
    warning: '#FFD166',
    danger: '#F72585',
    info: '#4CC9F0',
    light: '#F8F9FA',
    dark: '#212529',
  },
};

/**
 * Generates a gradient for canvas charts
 */
export const createGradient = (
  ctx: CanvasRenderingContext2D,
  colors: GradientColors,
  direction: 'vertical' | 'horizontal' = 'vertical'
): CanvasGradient => {
  const gradient = direction === 'vertical' 
    ? ctx.createLinearGradient(0, 0, 0, 400)
    : ctx.createLinearGradient(0, 0, 400, 0);
  
  gradient.addColorStop(0, colors.start);
  gradient.addColorStop(1, colors.end);
  
  return gradient;
};

/**
 * Generates color palette for multi-series charts
 */
export const generateColorPalette = (count: number, scheme: string = 'default'): string[] => {
  const baseColors = Object.values(colorSchemes[scheme] || colorSchemes.default);
  const colors: string[] = [];
  
  for (let i = 0; i < count; i++) {
    colors.push(baseColors[i % baseColors.length]);
  }
  
  return colors;
};

/**
 * Generates alpha variants of colors
 */
export const withAlpha = (color: string, alpha: number): string => {
  // Convert hex to rgba
  if (color.startsWith('#')) {
    const hex = color.replace('#', '');
    const r = parseInt(hex.substr(0, 2), 16);
    const g = parseInt(hex.substr(2, 2), 16);
    const b = parseInt(hex.substr(4, 2), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }
  
  // If already rgba, replace alpha
  if (color.startsWith('rgba')) {
    return color.replace(/[\d\.]+\)$/g, `${alpha})`);
  }
  
  // If rgb, convert to rgba
  if (color.startsWith('rgb')) {
    return color.replace('rgb', 'rgba').replace(')', `, ${alpha})`);
  }
  
  return color;
};

/**
 * Base chart options for consistent styling
 */
export const getBaseChartOptions = (theme: 'light' | 'dark' = 'light'): ChartOptions => {
  const colors = colorSchemes[theme === 'dark' ? 'dark' : 'default'];
  
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      intersect: false,
      mode: 'index',
    },
    plugins: {
      legend: {
        display: true,
        position: 'top',
        labels: {
          color: colors.dark,
          usePointStyle: true,
          padding: 20,
          font: {
            size: 12,
            family: 'Inter, system-ui, sans-serif',
          },
        },
      },
      tooltip: {
        backgroundColor: colors.dark,
        titleColor: colors.light,
        bodyColor: colors.light,
        borderColor: colors.secondary,
        borderWidth: 1,
        cornerRadius: 8,
        padding: 12,
        titleFont: {
          size: 14,
          weight: 'bold',
        },
        bodyFont: {
          size: 13,
        },
      },
    },
    scales: {
      x: {
        grid: {
          color: withAlpha(colors.secondary, 0.1),
          drawBorder: false,
        },
        ticks: {
          color: colors.secondary,
          font: {
            size: 11,
            family: 'Inter, system-ui, sans-serif',
          },
        },
      },
      y: {
        grid: {
          color: withAlpha(colors.secondary, 0.1),
          drawBorder: false,
        },
        ticks: {
          color: colors.secondary,
          font: {
            size: 11,
            family: 'Inter, system-ui, sans-serif',
          },
        },
      },
    },
  };
};

/**
 * Configuration for line charts
 */
export const getLineChartConfig = (
  data: ChartData<'line'>,
  options: Partial<ChartOptions<'line'>> = {}
): { type: 'line'; data: ChartData<'line'>; options: ChartOptions<'line'> } => {
  return {
    type: 'line',
    data,
    options: {
      ...getBaseChartOptions(),
      elements: {
        line: {
          tension: 0.4,
          borderWidth: 2,
        },
        point: {
          radius: 4,
          hoverRadius: 6,
          borderWidth: 2,
        },
      },
      ...options,
    },
  };
};

/**
 * Configuration for bar charts
 */
export const getBarChartConfig = (
  data: ChartData<'bar'>,
  options: Partial<ChartOptions<'bar'>> = {}
): { type: 'bar'; data: ChartData<'bar'>; options: ChartOptions<'bar'> } => {
  return {
    type: 'bar',
    data,
    options: {
      ...getBaseChartOptions(),
      elements: {
        bar: {
          borderRadius: 4,
          borderSkipped: false,
        },
      },
      ...options,
    },
  };
};

/**
 * Configuration for doughnut charts
 */
export const getDoughnutChartConfig = (
  data: ChartData<'doughnut'>,
  options: Partial<ChartOptions<'doughnut'>> = {}
): { type: 'doughnut'; data: ChartData<'doughnut'>; options: ChartOptions<'doughnut'> } => {
  const baseOptions = getBaseChartOptions();
  
  return {
    type: 'doughnut',
    data,
    options: {
      ...baseOptions,
      scales: undefined, // Remove scales for doughnut charts
      elements: {
        arc: {
          borderWidth: 2,
          borderColor: '#FFFFFF',
        },
      },
      cutout: '60%',
      ...options,
    },
  };
};

/**
 * Configuration for area charts
 */
export const getAreaChartConfig = (
  data: ChartData<'line'>,
  options: Partial<ChartOptions<'line'>> = {}
): { type: 'line'; data: ChartData<'line'>; options: ChartOptions<'line'> } => {
  // Ensure all datasets have fill: true for area effect
  const areaData = {
    ...data,
    datasets: data.datasets.map(dataset => ({
      ...dataset,
      fill: true,
      backgroundColor: dataset.backgroundColor || withAlpha(dataset.borderColor as string, 0.2),
    })),
  };

  return {
    type: 'line',
    data: areaData,
    options: {
      ...getBaseChartOptions(),
      elements: {
        line: {
          tension: 0.4,
          borderWidth: 2,
        },
        point: {
          radius: 0,
          hoverRadius: 4,
          borderWidth: 2,
        },
      },
      ...options,
    },
  };
};

/**
 * Custom tooltip formatter for performance metrics
 */
export const formatPerformanceTooltip = (context: TooltipItem<any>): string => {
  const { label, parsed, dataset } = context;
  const value = parsed.y || parsed;
  
  if (dataset.label?.toLowerCase().includes('response time')) {
    return `${label}: ${value.toFixed(2)}ms`;
  }
  
  if (dataset.label?.toLowerCase().includes('accuracy')) {
    return `${label}: ${(value * 100).toFixed(1)}%`;
  }
  
  if (dataset.label?.toLowerCase().includes('count')) {
    return `${label}: ${Math.round(value)}`;
  }
  
  return `${label}: ${value}`;
};

/**
 * Generates dataset configuration for time series
 */
export const createTimeSeriesDataset = (
  label: string,
  data: number[],
  colorIndex: number = 0,
  scheme: string = 'default'
): any => {
  const colors = generateColorPalette(8, scheme);
  const color = colors[colorIndex % colors.length];
  
  return {
    label,
    data,
    borderColor: color,
    backgroundColor: withAlpha(color, 0.2),
    borderWidth: 2,
    fill: false,
    tension: 0.4,
    pointRadius: 3,
    pointHoverRadius: 5,
    pointBackgroundColor: color,
    pointBorderColor: '#FFFFFF',
    pointBorderWidth: 2,
  };
};

/**
 * Creates a chart configuration for real-time updates
 */
export const getRealTimeChartConfig = (
  data: ChartData<'line'>,
  maxDataPoints: number = 50
): { type: 'line'; data: ChartData<'line'>; options: ChartOptions<'line'> } => {
  return {
    type: 'line',
    data,
    options: {
      ...getBaseChartOptions(),
      animation: {
        duration: 300,
      },
      elements: {
        line: {
          tension: 0.4,
          borderWidth: 2,
        },
        point: {
          radius: 2,
          hoverRadius: 4,
        },
      },
      scales: {
        x: {
          type: 'time',
          time: {
            displayFormats: {
              second: 'HH:mm:ss',
              minute: 'HH:mm',
              hour: 'HH:mm',
            },
          },
          grid: {
            color: withAlpha(colorSchemes.default.secondary, 0.1),
          },
          ticks: {
            maxTicksLimit: 10,
            color: colorSchemes.default.secondary,
          },
        },
        y: {
          grid: {
            color: withAlpha(colorSchemes.default.secondary, 0.1),
          },
          ticks: {
            color: colorSchemes.default.secondary,
          },
        },
      },
      plugins: {
        legend: {
          display: true,
          position: 'top',
        },
        tooltip: {
          mode: 'index',
          intersect: false,
          callbacks: {
            label: formatPerformanceTooltip,
          },
        },
      },
    },
  };
};

/**
 * Generates responsive breakpoints for charts
 */
export const getResponsiveOptions = (): ChartOptions['responsive'] => {
  return true;
};

/**
 * Creates a heatmap color scale
 */
export const createHeatmapColors = (value: number, min: number, max: number): string => {
  const normalized = (value - min) / (max - min);
  
  if (normalized <= 0.2) return '#10B981'; // Green
  if (normalized <= 0.4) return '#F59E0B'; // Yellow
  if (normalized <= 0.6) return '#F97316'; // Orange
  if (normalized <= 0.8) return '#EF4444'; // Red
  return '#DC2626'; // Dark Red
};

/**
 * Exports chart as image
 */
export const exportChartAsImage = (chartRef: any, filename: string): void => {
  if (chartRef?.current) {
    const canvas = chartRef.current.canvas;
    const url = canvas.toDataURL('image/png');
    const link = document.createElement('a');
    link.download = `${filename}.png`;
    link.href = url;
    link.click();
  }
};