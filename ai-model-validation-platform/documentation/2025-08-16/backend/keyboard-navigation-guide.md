# Keyboard Navigation Guide - AI Model Validation Platform

## Overview
This guide documents the keyboard navigation patterns implemented throughout the AI Model Validation Platform to ensure full accessibility compliance with WCAG 2.1 AA standards.

## Global Navigation Patterns

### Standard Navigation Keys
- **Tab**: Move forward through focusable elements
- **Shift + Tab**: Move backward through focusable elements
- **Enter**: Activate buttons, links, and form controls
- **Space**: Activate buttons and toggle controls
- **Escape**: Close modals, menus, and dropdowns
- **Arrow Keys**: Navigate within menus, lists, and grids

### Focus Indicators
All interactive elements display clear focus indicators:
- Blue outline (2px solid) with 2px offset
- High contrast (4.5:1 minimum ratio)
- Visible on all interactive elements

## Component-Specific Navigation

### Sidebar Navigation
- **Tab/Shift+Tab**: Navigate between menu items
- **Enter/Space**: Navigate to selected page
- **Escape**: Close mobile drawer (mobile only)

**ARIA Support:**
- `role="navigation"` on sidebar container
- `aria-label="Main navigation"`
- `role="menuitem"` on navigation links
- `aria-current="page"` for active page

### Header Navigation
- **Tab**: Move through notification button → user menu
- **Enter/Space**: Open user menu
- **Escape**: Close user menu
- **Arrow keys**: Navigate within user menu

**ARIA Support:**
- `aria-label="Open user menu"`
- `aria-haspopup="true"`
- `aria-expanded="true/false"`
- `role="menu"` on dropdown menu

### Dashboard Cards
- **Tab**: Navigate through statistic cards
- **Enter**: View detailed information (if applicable)
- Cards are focusable with descriptive labels

**ARIA Support:**
- `role="region"` on each card
- `aria-label` with full context
- `aria-live="polite"` for dynamic values

### Project Cards
- **Tab**: Navigate through project cards and actions
- **Enter/Space**: Open project details
- **Tab within card**: Focus on "View Details" button
- **More actions menu**: 
  - **Tab**: Focus menu trigger
  - **Enter/Space**: Open menu
  - **Arrow keys**: Navigate menu items
  - **Escape**: Close menu

**ARIA Support:**
- `role="button"` on project cards
- Comprehensive `aria-label` with project details
- `aria-controls` and `aria-expanded` for menus

### Forms and Inputs
- **Tab**: Navigate between form fields
- **Enter**: Submit forms or activate buttons
- **Space**: Toggle checkboxes and radio buttons
- **Arrow keys**: Navigate radio button groups

**Validation:**
- Errors announced via `aria-live="polite"`
- Required fields marked with `aria-required="true"`
- Invalid fields have `aria-invalid="true"`

### Data Tables
- **Tab**: Navigate between table controls
- **Arrow keys**: Navigate within table cells (if implemented)
- **Enter**: Activate table actions

### Modal Dialogs
- **Trap focus**: Focus remains within modal
- **Tab/Shift+Tab**: Cycle through modal elements
- **Escape**: Close modal
- **Enter**: Confirm actions
- Focus returns to trigger element on close

**ARIA Support:**
- `role="dialog"`
- `aria-labelledby` for modal title
- `aria-describedby` for modal content
- `aria-modal="true"`

### Loading States
- **Skip to content**: Avoid Tab-trapping in loading states
- Screen reader announcements for loading changes
- `role="status"` and `aria-live="polite"`

## Page-Specific Navigation

### Dashboard Page
1. **Header navigation** (Tab 1-3)
2. **Statistics cards** (Tab 4-7)
3. **Recent sessions list** (Tab 8+)
4. **System status indicators** (Continue tabbing)

### Projects Page
1. **Header navigation** (Tab 1-3)
2. **Action buttons** (Refresh, New Project) (Tab 4-5)
3. **Project cards** (Tab 6+)
   - Each card is one tab stop
   - Sub-navigation within each card

### Project Detail Page
1. **Header navigation**
2. **Project actions** (Edit, Delete)
3. **Tab navigation** through project sections
4. **Form controls** (if editing)

### Settings Page
1. **Header navigation**
2. **Settings categories** (sidebar if present)
3. **Form fields** in logical order
4. **Save/Reset buttons**

## Testing Checklist

### Basic Navigation
- [ ] All interactive elements are reachable via Tab
- [ ] Tab order follows logical flow
- [ ] Focus indicators are visible and high contrast
- [ ] Shift+Tab works in reverse order

### Keyboard Shortcuts
- [ ] Enter activates buttons and links
- [ ] Space activates buttons and toggles
- [ ] Escape closes modals and menus
- [ ] Arrow keys work in appropriate contexts

### Screen Reader Support
- [ ] All elements have appropriate ARIA labels
- [ ] Form validation is announced
- [ ] Dynamic content changes are announced
- [ ] Loading states are announced

### Focus Management
- [ ] Focus is trapped in modals
- [ ] Focus returns to trigger after modal closes
- [ ] Skip links are provided for main content
- [ ] No keyboard traps in normal flow

### Mobile Accessibility
- [ ] Touch targets meet 44px minimum
- [ ] Mobile navigation is keyboard accessible
- [ ] Responsive design maintains keyboard functionality

## Implementation Notes

### Focus Order Priority
1. **Skip links** (hidden until focused)
2. **Primary navigation**
3. **Main content** (heading first)
4. **Interactive elements** (forms, buttons)
5. **Secondary navigation** (pagination, etc.)

### Common Patterns
```typescript
// Focus indicator styling
'&:focus': {
  outline: '2px solid',
  outlineColor: 'primary.main',
  outlineOffset: 2,
}

// Keyboard event handling
const handleKeyDown = (event: React.KeyboardEvent) => {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault();
    handleAction();
  }
  if (event.key === 'Escape') {
    handleClose();
  }
};

// ARIA pattern for menus
<Button
  aria-controls={open ? 'menu-id' : undefined}
  aria-haspopup="true"
  aria-expanded={open ? 'true' : 'false'}
  onClick={handleClick}
>
  Menu
</Button>
```

### Testing Tools
1. **Browser testing**: Use Tab key to navigate entire application
2. **Screen reader testing**: NVDA, JAWS, VoiceOver
3. **Automated testing**: axe-core, Testing Library
4. **Keyboard-only testing**: Disable mouse/trackpad

## Compliance Standards

### WCAG 2.1 AA Requirements Met
- **2.1.1 Keyboard**: All functionality available via keyboard
- **2.1.2 No Keyboard Trap**: No keyboard traps exist
- **2.4.3 Focus Order**: Logical and intuitive focus order
- **2.4.7 Focus Visible**: Clear focus indicators
- **3.2.1 On Focus**: No unexpected context changes
- **3.2.2 On Input**: No unexpected context changes

### Additional Enhancements
- Enhanced focus indicators beyond minimum requirements
- Comprehensive ARIA labeling
- Logical tab order optimization
- Mobile keyboard accessibility
- Screen reader optimizations

## Browser Support
- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

All keyboard navigation patterns tested across supported browsers.