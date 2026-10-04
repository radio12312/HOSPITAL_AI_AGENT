import { X } from 'lucide-react'
import { useEffect, useId, useRef, type ReactNode } from 'react'

interface ModalProps {
  open: boolean
  title: string
  description?: string
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
  size?: 'md' | 'lg'
}

/** Native <dialog> modal: gives focus trapping, Esc-to-close and top-layer rendering for free. */
export function Modal({ open, title, description, onClose, children, footer, size = 'md' }: ModalProps) {
  const ref = useRef<HTMLDialogElement>(null)
  const titleId = useId()
  const descId = useId()

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      aria-describedby={description ? descId : undefined}
      onCancel={(e) => {
        e.preventDefault()
        onClose()
      }}
      onClick={(e) => {
        // Click on the backdrop (the dialog element itself) closes.
        if (e.target === e.currentTarget) onClose()
      }}
      className={`m-auto w-[calc(100%-2rem)] rounded-xl border border-slate-200 bg-white p-0 text-slate-900 shadow-xl backdrop:bg-slate-900/40 ${size === 'lg' ? 'max-w-2xl' : 'max-w-lg'}`}
    >
      {open && (
        <div className="flex max-h-[85vh] flex-col">
          <header className="flex items-start justify-between gap-4 border-b border-slate-100 px-6 py-4">
            <div>
              <h2 id={titleId} className="text-base font-semibold text-slate-900">
                {title}
              </h2>
              {description && (
                <p id={descId} className="mt-0.5 text-sm text-slate-500">
                  {description}
                </p>
              )}
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close dialog"
              className="cursor-pointer rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
            >
              <X size={18} aria-hidden="true" />
            </button>
          </header>
          <div className="overflow-y-auto px-6 py-5">{children}</div>
          {footer && (
            <footer className="flex justify-end gap-2 border-t border-slate-100 bg-slate-50 px-6 py-3">{footer}</footer>
          )}
        </div>
      )}
    </dialog>
  )
}
