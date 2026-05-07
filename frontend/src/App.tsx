import { RouterProvider } from 'react-router-dom'
import { Toaster } from 'sonner'
import { router } from './routes'

function App() {
  return (
    <>
      <RouterProvider router={router} />
      <Toaster
        theme="dark"
        position="top-right"
        toastOptions={{
          style: {
            background: '#0f172a',
            border: '1px solid #1e293b',
            color: '#e2e8f0',
          },
        }}
      />
    </>
  )
}

export default App
