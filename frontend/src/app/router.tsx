import { createBrowserRouter } from "react-router-dom";
import { MainLayout } from "../components/layout/MainLayout";
import { modules } from "../components/layout/AppSidebar";
import { DashboardPage } from "../features/dashboard/DashboardPage";
import { PlaceholderPage } from "../features/PlaceholderPage";
import { SettingsPage } from "../features/settings/SettingsPage";
import { AnalyticsPage } from "../features/gsc/AnalyticsPage";
import { lazy, Suspense } from "react";
const KeywordPage = lazy(() =>
  import("../features/keywords/KeywordPage").then((module) => ({
    default: module.KeywordPage,
  })),
);
const AIWorkspacePage = lazy(() =>
  import("../features/ai/AIWorkspacePage").then((module) => ({
    default: module.AIWorkspacePage,
  })),
);
import { TechnicalPage } from "../features/technical/TechnicalPage";

export const router = createBrowserRouter([
  {
    element: <MainLayout />,
    children: [
      { path: "/", element: <DashboardPage /> },
      { path: "/settings", element: <SettingsPage /> },
      { path: "/gsc-analytics", element: <AnalyticsPage /> },
      { path: "/technical-seo", element: <TechnicalPage /> },
      {
        path: "/ai-workspace",
        element: (
          <Suspense fallback={<p role="status">Đang tải AI Workspace…</p>}>
            <AIWorkspacePage />
          </Suspense>
        ),
      },
      {
        path: "/keyword-tracking",
        element: (
          <Suspense fallback={<p role="status">Đang tải Theo dõi từ khóa…</p>}>
            <KeywordPage />
          </Suspense>
        ),
      },
      ...modules
        .slice(1)
        .filter(
          (module) =>
            ![
              "/settings",
              "/gsc-analytics",
              "/technical-seo",
              "/keyword-tracking",
              "/ai-workspace",
            ].includes(module.path),
        )
        .map((module) => ({ path: module.path, element: <PlaceholderPage /> })),
      { path: "*", element: <PlaceholderPage /> },
    ],
  },
]);
