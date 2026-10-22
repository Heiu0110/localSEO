import { createBrowserRouter } from 'react-router-dom';
import { MainLayout } from '../components/layout/MainLayout';
import { modules } from '../components/layout/AppSidebar';
import { DashboardPage } from '../features/dashboard/DashboardPage';
import { PlaceholderPage } from '../features/PlaceholderPage';
import { SettingsPage } from '../features/settings/SettingsPage';
import { AnalyticsPage } from '../features/gsc/AnalyticsPage';
import { TechnicalPage } from '../features/technical/TechnicalPage';

export const router = createBrowserRouter([
  { element: <MainLayout />, children: [
    { path: '/', element: <DashboardPage /> },
    { path: '/settings', element: <SettingsPage /> },
    { path: '/gsc-analytics', element: <AnalyticsPage /> },
    { path: '/technical-seo', element: <TechnicalPage /> },
    ...modules.slice(1).filter(module=>!['/settings','/gsc-analytics','/technical-seo'].includes(module.path)).map(module => ({ path: module.path, element: <PlaceholderPage /> })),
    { path: '*', element: <PlaceholderPage /> },
  ] },
]);
