// Runs before every unit test file.
// Adds readable DOM assertions such as `expect(element).toBeInTheDocument()`.
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// Unmount rendered components after each test so tests never affect each other.
afterEach(() => {
  cleanup()
})
