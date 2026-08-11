import { useColorScheme } from 'frappe-ui'

type Theme = 'light' | 'dark' | 'system'

/**
 * Thin wrapper around frappe-ui's `useColorScheme` that keeps Pilot's
 * `setTheme` / `currentTheme` call sites unchanged.
 *
 * frappe-ui already mutes transitions during the swap, so the old
 * `no-transition` dance here is no longer needed.
 */
export const useTheme = () => {
  const { colorScheme, setColorScheme, toggleColorScheme } = useColorScheme()

  const setTheme = (theme: Theme) => {
    setColorScheme(theme)
  }

  return {
    currentTheme: colorScheme,
    setTheme,
    colorScheme,
    setColorScheme,
    toggleColorScheme,
  }
}
