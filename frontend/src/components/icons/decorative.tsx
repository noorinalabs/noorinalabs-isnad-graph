/**
 * Decorative SVG elements — Islamic geometric patterns.
 *
 * All elements use currentColor, work in light/dark mode,
 * and are inline-friendly.
 */
import type { SVGProps } from 'react'

/**
 * Repeating Islamic geometric border pattern.
 * Renders as a horizontal divider with interlocking octagonal motifs.
 * Width fills container; height is fixed at 12px.
 */
export function GeometricBorder({
  className,
  style,
  ...props
}: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 200 12"
      preserveAspectRatio="none"
      fill="none"
      stroke="currentColor"
      strokeWidth="0.8"
      aria-hidden="true"
      className={className}
      style={{ width: '100%', height: 12, opacity: 0.3, ...style }}
      {...props}
    >
      {/* Repeating octagonal / interlocking diamond pattern */}
      <defs>
        <pattern id="geo-border-pat" x="0" y="0" width="20" height="12" patternUnits="userSpaceOnUse">
          {/* Diamond */}
          <path d="M10 1l4 5-4 5-4-5z" />
          {/* Connecting lines */}
          <path d="M0 6h6M14 6h6" />
          {/* Small accent squares at intersections */}
          <rect x="9" y="5" width="2" height="2" fill="currentColor" opacity="0.4" transform="rotate(45 10 6)" />
        </pattern>
      </defs>
      <rect width="200" height="12" fill="url(#geo-border-pat)" stroke="none" />
    </svg>
  )
}

/**
 * Octagonal frame — wraps content (like a logo) in an octagonal border.
 * Meant to be sized via CSS on the container.
 */
export function OctagonalFrame({
  className,
  style,
  ...props
}: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 100 100"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      aria-hidden="true"
      className={className}
      style={{ opacity: 0.5, ...style }}
      {...props}
    >
      {/* Outer octagon */}
      <polygon points="30,2 70,2 98,30 98,70 70,98 30,98 2,70 2,30" />
      {/* Inner octagon */}
      <polygon points="35,10 65,10 90,35 90,65 65,90 35,90 10,65 10,35" strokeDasharray="4 3" strokeWidth="1" />
      {/* Corner accent diamonds */}
      <path d="M15 15l3 3-3 3-3-3z" fill="currentColor" opacity="0.3" />
      <path d="M85 15l3 3-3 3-3-3z" fill="currentColor" opacity="0.3" />
      <path d="M15 85l3 3-3 3-3-3z" fill="currentColor" opacity="0.3" />
      <path d="M85 85l3 3-3 3-3-3z" fill="currentColor" opacity="0.3" />
    </svg>
  )
}

/**
 * Page header geometric accent — small decorative element
 * that sits beside page titles. Renders an interlocking
 * geometric motif inspired by Islamic tilework.
 */
export function PageHeaderAccent({
  className,
  style,
  ...props
}: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="-2 -2 36 28"
      fill="none"
      stroke="currentColor"
      strokeWidth="1"
      aria-hidden="true"
      className={className}
      style={{ width: 36, height: 28, opacity: 0.35, overflow: 'visible', ...style }}
      {...props}
    >
      {/* Interlocking squares forming 8-pointed star fragment */}
      <rect x="8" y="4" width="16" height="16" rx="1" transform="rotate(0 16 12)" />
      <rect x="8" y="4" width="16" height="16" rx="1" transform="rotate(45 16 12)" />
      {/* Center dot */}
      <circle cx="16" cy="12" r="1.5" fill="currentColor" stroke="none" opacity="0.5" />
    </svg>
  )
}
