import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AppErrorBoundary } from './AppErrorBoundary'

function BrokenChild(): never {
  throw new Error('expected boundary test')
}

describe('AppErrorBoundary', () => {
  let preventExpectedError: ((event: ErrorEvent) => void) | undefined

  afterEach(() => {
    if (preventExpectedError) {
      window.removeEventListener('error', preventExpectedError)
      preventExpectedError = undefined
    }
    vi.restoreAllMocks()
  })

  it('shows the error page when a child throws', () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
    preventExpectedError = (event) => event.preventDefault()
    window.addEventListener('error', preventExpectedError)

    render(
      <MemoryRouter>
        <AppErrorBoundary>
          <BrokenChild />
        </AppErrorBoundary>
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: 'Something went wrong.' })).toBeVisible()
    expect(screen.getByRole('link', { name: 'Return to status' })).toHaveAttribute('href', '/')
  })
})
