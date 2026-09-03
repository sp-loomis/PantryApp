/**
 * @pantry-app/shared
 *
 * Platform-agnostic business logic for Pantry App
 */

// Config
export { getApiBaseUrl, getAuthMode, LOCAL_DEV_USER } from './config/env.js';

// Auth services
export {
  signUpUser,
  confirmUserSignUp,
  signInUser,
  signOutUser,
  getCurrentAuthUser
} from './services/authService.js';
export { getAuthToken } from './services/authTokens.js';

// API + inventory services
export { api, request, ApiError } from './services/apiClient.js';
export {
  listLocations,
  getLocation,
  createLocation,
  updateLocation,
  deleteLocation,
  listItems,
  getItem,
  createItem,
  updateItem,
  deleteItem,
  getItemTags,
  addItemTags,
  removeItemTag,
  listTags,
  searchItems
} from './services/inventoryService.js';

// Hooks
export { useAuth } from './hooks/useAuth.js';
export { useInventory } from './hooks/useInventory.js';

// Utils
export {
  validateEmail,
  validatePassword,
  validatePasswordConfirmation,
  validateVerificationCode,
  validateItemName,
  validateLocationName
} from './utils/validation.js';
export {
  MEASURE_TYPES,
  UNITS,
  DEFAULT_UNIT,
  EMPTY_MEASURE,
  isValidUnit,
  validateMeasure,
  measureToDimensions,
  dimensionsToMeasure,
  formatDimension,
  formatMeasure
} from './utils/dimensions.js';
