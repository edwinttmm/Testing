module.exports = {
  extends: ['./.eslintrc.development.js'],
  rules: {
    // Temporarily relax strict rules for development
    '@typescript-eslint/no-explicit-any': 'warn',
    '@typescript-eslint/no-unused-vars': 'warn',
    'no-console': 'warn',
    'react-hooks/exhaustive-deps': 'warn',
    'no-restricted-globals': 'warn',
    'jest/no-conditional-expect': 'warn',
    'import/no-anonymous-default-export': 'warn',
    'no-mixed-operators': 'warn'
  }
};