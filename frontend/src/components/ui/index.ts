// Re-export all UI components from @noorinalabs/design-system.
// Local component files are kept as fallbacks in case the design-system
// versions diverge in API. To revert to local components, change the
// import source back to "./ComponentName".
//
// TODO: Once @noorinalabs/design-system is published (requires a v* tag push
// on noorinalabs-design-system to trigger the publish workflow), run
// `npm install` to pull the package from the registry. Until then, the
// package is installed from the local filesystem during development.

export { Button, buttonVariants } from "@noorinalabs/design-system"
export type { ButtonProps } from "@noorinalabs/design-system"

export { Input } from "@noorinalabs/design-system"
export type { InputProps } from "@noorinalabs/design-system"

export {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from "@noorinalabs/design-system"

export {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogOverlay,
  DialogPortal,
  DialogTitle,
  DialogTrigger,
} from "@noorinalabs/design-system"

export {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from "@noorinalabs/design-system"

export { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@noorinalabs/design-system"

export { Badge, badgeVariants } from "@noorinalabs/design-system"
export type { BadgeProps } from "@noorinalabs/design-system"

export { Tabs, TabsContent, TabsList, TabsTrigger } from "@noorinalabs/design-system"
