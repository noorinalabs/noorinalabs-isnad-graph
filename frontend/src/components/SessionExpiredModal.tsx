import { useAuth } from '../hooks/useAuth'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from './ui/Dialog'
import { Button } from './ui/Button'

export default function SessionExpiredModal() {
  const { sessionExpired, dismissSessionExpired } = useAuth()

  return (
    <Dialog open={sessionExpired}>
      <DialogContent
        onInteractOutside={(e) => e.preventDefault()}
        onEscapeKeyDown={(e) => e.preventDefault()}
      >
        <DialogHeader>
          <DialogTitle>Session expired</DialogTitle>
          <DialogDescription>
            Your session has expired. Please sign in again.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button onClick={dismissSessionExpired}>Sign In</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
