import * as TooltipPrimitive from '@radix-ui/react-tooltip';
import type { ReactNode } from 'react';

export function Tooltip({ text, children }: { text: string; children: ReactNode }) {
  return <TooltipPrimitive.Root><TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
    <TooltipPrimitive.Portal><TooltipPrimitive.Content sideOffset={7} className="tooltip-content">{text}<TooltipPrimitive.Arrow className="tooltip-arrow" /></TooltipPrimitive.Content></TooltipPrimitive.Portal>
  </TooltipPrimitive.Root>;
}
export const TooltipProvider = TooltipPrimitive.Provider;
