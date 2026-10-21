import { createBrowserRouter } from 'react-router-dom';
import { MainLayout } from '../components/layout/MainLayout';
import { modules } from '../components/layout/AppSidebar';
import { DashboardPage } from '../features/dashboard/DashboardPage';
import { PlaceholderPage } from '../features/PlaceholderPage';

export const router = createBrowserRouter([
  { element: <MainLayout />, children: [
    { path: '/', element: <DashboardPage /> },
    ...modules.slice(1).map(module => ({ path: module.path, element: <PlaceholderPage /> })),
    { path: '*', element: <PlaceholderPage /> },
  ] },
]);
