// Opens a tab through the menu, as FRANKS would: on a phone, the folder in the
// bottom bar then the tab in the top bar; on a PC, the tab in the sidebar.
import { expect, type Page } from '@playwright/test'

export type FolderName = 'Entraînement' | 'Santé' | 'Coach'

export async function openTab(page: Page, folder: FolderName | 'Réglages', tab: string) {
  const bottomBar = page.getByRole('navigation', { name: 'Dossiers' })
  const sidebar = page.getByRole('navigation', { name: 'Menu' })
  // The frame appears once the sign-in check has answered: wait for one menu.
  await expect(bottomBar.or(sidebar)).toBeVisible()
  if (await bottomBar.isVisible()) {
    if (folder === 'Réglages') await page.getByRole('link', { name: 'Réglages' }).click()
    else await bottomBar.getByRole('link', { name: folder }).click()
    const tabs = page.getByRole('navigation', { name: `Onglets ${folder}` })
    await tabs.getByRole('link', { name: tab, exact: true }).click()
  } else {
    await sidebar.getByRole('link', { name: tab, exact: true }).click()
  }
  // The tab is lit up once its page is open.
  const current = page.locator('a[aria-current="page"]:visible')
  await expect(current.filter({ hasText: new RegExp(`^${tab}$`) }).first()).toBeVisible()
}
