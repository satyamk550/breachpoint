const configuredName = import.meta.env.VITE_APP_NAME?.trim()

export const brand = {
  name: configuredName || 'Breachpoint',
  tagline: 'Team CTF platform',
} as const

export function applyBrandMetadata() {
  document.title = `${brand.name} | ${brand.tagline}`

  const description = document.querySelector<HTMLMetaElement>('meta[name="description"]')
  if (description) {
    description.content = `${brand.name}, ${brand.tagline}.`
  }

  const themeColor = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]')
  if (themeColor) {
    themeColor.content = getComputedStyle(document.documentElement)
      .getPropertyValue('--color-bg')
      .trim()
  }
}
