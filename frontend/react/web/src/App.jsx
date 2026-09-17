/**
 * Main App Component
 *
 * Sets up providers and routing. Auth pages are public; all inventory pages
 * live under a protected layout route that renders the responsive AppShell.
 */

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ChakraProvider } from '@chakra-ui/react';
import { AuthProvider } from './contexts/AuthContext';
import { InventoryProvider } from './contexts/InventoryContext';
import ProtectedRoute from './components/ProtectedRoute';
import AppShell from './components/AppShell';
import LoginPage from './pages/LoginPage';
import SignupPage from './pages/SignupPage';
import ConfirmPage from './pages/ConfirmPage';
import SearchPage from './pages/SearchPage';
import LocationsPage from './pages/LocationsPage';
import LocationDetailPage from './pages/LocationDetailPage';
import LocationFormPage from './pages/LocationFormPage';
import CategoriesPage from './pages/CategoriesPage';
import CategoryFormPage from './pages/CategoryFormPage';
import ItemDetailPage from './pages/ItemDetailPage';
import ItemFormPage from './pages/ItemFormPage';
import TagsPage from './pages/TagsPage';
import TagDetailPage from './pages/TagDetailPage';
import TasksDashboardPage from './pages/TasksDashboardPage';
import TaskDetailPage from './pages/TaskDetailPage';
import TaskFormPage from './pages/TaskFormPage';
import MessageLogPage from './pages/MessageLogPage';
import ReportsPage from './pages/ReportsPage';
import ReportFormPage from './pages/ReportFormPage';
import SettingsPage from './pages/SettingsPage';
import IntegrationsPage from './pages/IntegrationsPage';
import theme from './theme/theme';

/** Protected layout: auth gate + inventory state + the app nav shell. */
function ProtectedLayout() {
  return (
    <ProtectedRoute>
      <InventoryProvider>
        <AppShell />
      </InventoryProvider>
    </ProtectedRoute>
  );
}

function App() {
  return (
    <ChakraProvider theme={theme}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            {/* Public auth routes */}
            <Route path="/login" element={<LoginPage />} />
            <Route path="/signup" element={<SignupPage />} />
            <Route path="/confirm" element={<ConfirmPage />} />

            {/* Protected inventory app */}
            <Route element={<ProtectedLayout />}>
              <Route path="/" element={<SearchPage />} />
              <Route path="/locations" element={<LocationsPage />} />
              <Route path="/locations/new" element={<LocationFormPage />} />
              <Route path="/locations/:locationId" element={<LocationDetailPage />} />
              <Route path="/locations/:locationId/edit" element={<LocationFormPage />} />
              <Route path="/categories" element={<CategoriesPage />} />
              <Route path="/categories/new" element={<CategoryFormPage />} />
              <Route path="/categories/:categoryId/edit" element={<CategoryFormPage />} />
              <Route path="/items/new" element={<ItemFormPage />} />
              <Route path="/items/:itemId" element={<ItemDetailPage />} />
              <Route path="/items/:itemId/edit" element={<ItemFormPage />} />
              <Route path="/tasks" element={<TasksDashboardPage />} />
              <Route path="/tasks/new" element={<TaskFormPage />} />
              <Route path="/tasks/:taskId" element={<TaskDetailPage />} />
              <Route path="/tasks/:taskId/edit" element={<TaskFormPage />} />
              <Route path="/tags" element={<TagsPage />} />
              <Route path="/tags/:tag" element={<TagDetailPage />} />
              <Route path="/messages" element={<MessageLogPage />} />
              <Route path="/reports" element={<ReportsPage />} />
              <Route path="/reports/new" element={<ReportFormPage />} />
              <Route path="/reports/:reportId/edit" element={<ReportFormPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/settings/integrations" element={<IntegrationsPage />} />
            </Route>

            {/* Unknown routes → home */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ChakraProvider>
  );
}

export default App;
