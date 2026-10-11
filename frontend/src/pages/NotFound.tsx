import { Link } from "@/components/AppLink";
import { LinkButton } from "@/components/Button";

export function NotFoundPage() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center px-4 text-center">
      <h1 className="font-display text-7xl font-bold">404</h1>
      <h2 className="mt-4 text-xl font-semibold">Page not found</h2>
      <p className="mt-2 text-sm text-muted-foreground">The page you're looking for doesn't exist or has been moved.</p>
      <LinkButton to="/" className="mt-6">
        Go home
      </LinkButton>
      <p className="mt-6 text-xs text-muted-foreground">
        <Link to="/marketplace" className="underline">
          Browse the marketplace instead
        </Link>
      </p>
    </div>
  );
}
