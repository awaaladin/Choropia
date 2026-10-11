import { Link as RouterLink, NavLink as RouterNavLink, type LinkProps, type NavLinkProps } from "react-router";

/** Every in-app link animates the page change via the browser's View Transitions API. */
export function Link(props: LinkProps) {
  return <RouterLink viewTransition {...props} />;
}

export function NavLink(props: NavLinkProps) {
  return <RouterNavLink viewTransition {...props} />;
}
