import './index.css'
import './i18n'

import { QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from '@tanstack/react-router'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { createQueryClient } from './lib/query-client'
import { createAppRouter } from './router'

const queryClient = createQueryClient()
const router = createAppRouter(queryClient)

const root = document.getElementById('root')
if (!root) throw new Error('index.html has no #root element.')

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
)
