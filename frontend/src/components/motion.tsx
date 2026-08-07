// Motion vocabulary for the whole app. Quiet and paper-like: things settle
// into place, nothing bounces. Durations short enough that the demo never
// waits on an animation.
import { AnimatePresence, motion } from 'framer-motion'
import type { ReactNode } from 'react'

const EASE = [0.22, 0.61, 0.36, 1] as const

/** Wraps a screen: fades up 8px on enter. Keyed by route in App.tsx. */
export function Page({ children }: { children: ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -4 }}
      transition={{ duration: 0.22, ease: EASE }}
    >
      {children}
    </motion.div>
  )
}

/** Stagger container for record lists. */
export function Stack({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <motion.div
      className={className}
      initial="hidden"
      animate="show"
      variants={{ show: { transition: { staggerChildren: 0.04 } } }}
    >
      {children}
    </motion.div>
  )
}

/** One staggered child — pair with <Stack>. */
export function Item({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <motion.div
      className={className}
      variants={{
        hidden: { opacity: 0, y: 10 },
        show: { opacity: 1, y: 0, transition: { duration: 0.28, ease: EASE } },
      }}
    >
      {children}
    </motion.div>
  )
}

/** Height-animated reveal for toggles and inline panels. */
export function Reveal({ open, children }: { open: boolean; children: ReactNode }) {
  return (
    <AnimatePresence initial={false}>
      {open && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={{ opacity: 0, height: 0 }}
          transition={{ duration: 0.24, ease: EASE }}
          style={{ overflow: 'hidden' }}
        >
          {children}
        </motion.div>
      )}
    </AnimatePresence>
  )
}

export { AnimatePresence, motion }
