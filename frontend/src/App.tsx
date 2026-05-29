import { useEffect } from 'react'
import { Toaster } from 'sonner'
import { Dashboard } from './features/dashboard/dashboard'
import { useUiStore } from './store/ui-store'

function App() {
  const { setCommandOpen } = useUiStore()

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setCommandOpen(true)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [setCommandOpen])

  return (
    <>
      <Dashboard />
      <Toaster position="top-right" richColors closeButton />
    </>
  )
}

export default App
