/** React facade for the app-wide new-task command. */

import { useRouter } from 'next/router';
import React, { createContext, useCallback, useContext, useEffect, useRef } from 'react';

import type { NewTaskCoordinator, NewTaskGuard } from './coordinator';
import { createNewTaskCoordinator } from './coordinator';

const NewTaskContext = createContext<NewTaskCoordinator | null>(null);

function useCoordinator(): NewTaskCoordinator {
  const coordinator = useContext(NewTaskContext);
  if (!coordinator) {
    throw new Error('New-task hooks must be used within NewTaskProvider.');
  }
  return coordinator;
}

export function NewTaskProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const routerRef = useRef(router);
  routerRef.current = router;

  const coordinatorRef = useRef<NewTaskCoordinator | null>(null);
  if (!coordinatorRef.current) {
    const getBrowserLocation = () => {
      if (typeof window === 'undefined') return null;
      return {
        pathname: window.location.pathname.replace(/\/$/, '') || '/',
        hasQueryOrHash: Boolean(window.location.search || window.location.hash),
      };
    };

    const getCanonicalPath = () => {
      const browserLocation = getBrowserLocation();
      const currentPathname = browserLocation?.pathname ?? routerRef.current.pathname;
      return currentPathname === '/lishui/chat' ? '/lishui/chat' : '/';
    };

    coordinatorRef.current = createNewTaskCoordinator({
      isCanonicalHome: () => {
        const browserLocation = getBrowserLocation();
        if (browserLocation) {
          return browserLocation.pathname === getCanonicalPath() && !browserLocation.hasQueryOrHash;
        }

        const current = routerRef.current;
        const pathWithoutHash = current.asPath.split('#', 1)[0];
        const hasQuery = pathWithoutHash.includes('?');
        const currentPath = pathWithoutHash.split('?', 1)[0].replace(/\/$/, '') || '/';
        return currentPath === getCanonicalPath() && !hasQuery;
      },
      goCanonicalHome: async () => {
        const current = routerRef.current;
        const targetPath = getCanonicalPath();
        await current.replace(targetPath, undefined, { shallow: current.pathname === targetPath });
      },
    });
  }

  return <NewTaskContext.Provider value={coordinatorRef.current}>{children}</NewTaskContext.Provider>;
}

/** Return the single app-wide command used by every "new task" affordance. */
export function useStartNewTask(): () => Promise<void> {
  const coordinator = useCoordinator();
  return useCallback(() => coordinator.begin(), [coordinator]);
}

/** Attach the mounted task workspace that owns the reset implementation. */
export function useNewTaskOwner(resetForNewTask: () => void): void {
  const coordinator = useCoordinator();
  const resetRef = useRef(resetForNewTask);
  resetRef.current = resetForNewTask;

  useEffect(() => coordinator.attach(() => resetRef.current()), [coordinator]);
}

/**
 * Attach a guard consulted before every command. Resolve false to cancel the
 * command (e.g. while a turn is in flight and the user declines the
 * interruption confirmation).
 */
export function useNewTaskGuard(guard: NewTaskGuard): void {
  const coordinator = useCoordinator();
  const guardRef = useRef(guard);
  guardRef.current = guard;

  useEffect(() => coordinator.attachGuard(() => guardRef.current()), [coordinator]);
}
