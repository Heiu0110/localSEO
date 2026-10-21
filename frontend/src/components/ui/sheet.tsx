import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import type { ReactNode } from 'react';
import { Button } from './button';

export function Sheet({ open, onOpenChange, title, description, children }: { open: boolean; onOpenChange: (open: boolean) => void; title: string; description: string; children: ReactNode }) {
  return <Dialog.Root open={open} onOpenChange={onOpenChange}><Dialog.Portal>
    <Dialog.Overlay className="sheet-overlay" />
    <Dialog.Content className="sheet-content"><div className="sheet-heading"><div><p className="eyebrow">PAGE EXPLORER</p><Dialog.Title>{title}</Dialog.Title></div>
      <Dialog.Close asChild><Button variant="ghost" size="icon" aria-label="Close page details"><X size={19} /></Button></Dialog.Close></div>
      <Dialog.Description className="sheet-description">{description}</Dialog.Description>{children}
    </Dialog.Content>
  </Dialog.Portal></Dialog.Root>;
}
