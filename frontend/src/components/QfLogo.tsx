// The app's own QF logo (FRANKS's logo). It is red on a transparent background, so it
// sits on a white rounded tile: readable on the blue frame and in night mode too.
import logo from '../assets/logo.png'

export default function QfLogo({ size = 38 }: { size?: number }) {
  // Decorative: the callers write "App Sport" or an aria-label next to it.
  return (
    <span
      className="qf-logo"
      style={{ width: size, height: size, padding: size * 0.08 }}
      aria-hidden="true"
    >
      <img src={logo} alt="" />
    </span>
  )
}
