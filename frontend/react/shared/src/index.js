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
export {
  listCategories,
  getCategory,
  createCategory,
  updateCategory,
  deleteCategory,
  listMeasureUnits
} from './services/categoryService.js';
export {
  listTasks,
  getTask,
  createTask,
  updateTask,
  deleteTask,
  completeTask,
  uncompleteTask
} from './services/taskService.js';
export {
  listReports,
  getReport,
  createReport,
  updateReport,
  deleteReport,
  runReport
} from './services/reportService.js';
export {
  listMessages,
  listUnread,
  getMessage,
  markRead,
  markUnread,
  deleteMessage
} from './services/messageService.js';
export {
  getAuthorizeUrl,
  listConnections,
  listChannels,
  disconnect as disconnectSlack,
  testConnection as testSlackConnection,
  devStubConnect as devStubConnectSlack
} from './services/slackService.js';

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
  validateLocationName,
  validateTaskName,
  validateRecurrence,
  validateReportName,
  validateSchedule
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
