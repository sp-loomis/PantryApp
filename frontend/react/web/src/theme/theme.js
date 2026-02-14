/**
 * Chakra UI Theme Configuration
 *
 * Custom theme for Pantry App.
 * Focuses on functionality over visual polish.
 */

import { extendTheme } from '@chakra-ui/react';

const theme = extendTheme({
  config: {
    initialColorMode: 'light',
    useSystemColorMode: false
  },
  styles: {
    global: {
      body: {
        bg: 'gray.50'
      }
    }
  },
  colors: {
    brand: {
      50: '#e3f2fd',
      100: '#bbdefb',
      200: '#90caf9',
      300: '#64b5f6',
      400: '#42a5f5',
      500: '#2196f3',
      600: '#1e88e5',
      700: '#1976d2',
      800: '#1565c0',
      900: '#0d47a1'
    }
  },
  components: {
    Button: {
      defaultProps: {
        colorScheme: 'brand'
      }
    },
    Input: {
      defaultProps: {
        focusBorderColor: 'brand.500'
      }
    }
  }
});

export default theme;
