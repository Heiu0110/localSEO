import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider } from 'react-router-dom';
import { TooltipProvider } from '../components/ui/tooltip';
import { router } from './router';

const client = new QueryClient({ defaultOptions: { queries: { staleTime: 5 * 60 * 1000, retry: 1, refetchOnWindowFocus: false } } });
export function App() {
  return <QueryClientProvider client={client}><TooltipProvider delayDuration={250}><RouterProvider router={router} /></TooltipProvider></QueryClientProvider>;
}
