import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Plus, SearchX } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router";
import { LinkButton, Button } from "@/components/Button";
import { ListingCard } from "@/components/ListingCard";
import { EmptyState, ErrorState, Field, Input, ListingSkeleton, Pill, Select } from "@/components/ui";
import { api, rows } from "@/lib/api";
import { usePrefs } from "@/lib/prefs";
import { cn } from "@/lib/utils";

const KEYS = ["search", "condition", "min_price", "max_price", "ordering", "category"] as const;

export function MarketplacePage() {
  const prefs = usePrefs();
  const [params, setParams] = useSearchParams();
  const active = Object.fromEntries(KEYS.map((k) => [k, params.get(k) ?? ""])) as Record<(typeof KEYS)[number], string>;

  // The form edits a draft; "Apply" (or Enter) commits it to the URL, which drives the query.
  const [draft, setDraft] = useState(active);
  useEffect(() => setDraft(active), [params]); // eslint-disable-line react-hooks/exhaustive-deps

  const commit = (next: Partial<typeof active>) => {
    const merged = { ...active, ...next };
    const search = new URLSearchParams();
    KEYS.forEach((k) => merged[k] && search.set(k, merged[k]));
    setParams(search, { viewTransition: true });
  };
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    commit(draft);
  };

  const categories = useQuery({ queryKey: ["categories"], queryFn: api.listCategories, staleTime: 10 * 60_000 });
  const listings = useQuery({
    queryKey: ["listings", active],
    queryFn: async () => {
      const data = await api.listListings(Object.fromEntries(Object.entries(active).filter(([, v]) => v)));
      return { items: rows(data), count: Array.isArray(data) ? data.length : (data.count ?? rows(data).length) };
    },
    placeholderData: keepPreviousData,
  });

  const items = listings.data?.items ?? [];
  const hasFilters = KEYS.some((k) => active[k]);

  return (
    <div className="mx-auto max-w-6xl">
      <div className="editorial-enter flex items-end justify-between gap-4">
        <div>
          <span className="text-xs font-semibold uppercase tracking-widest text-primary">Escrow-protected listings</span>
          <h1 className="text-2xl font-bold">Marketplace</h1>
        </div>
        <LinkButton to="/listings/new">
          <Plus size={15} /> New listing
        </LinkButton>
      </div>

      <div className="editorial-enter mt-5 flex items-center gap-2 overflow-x-auto pb-1" style={prefs.stagger(0)}>
        <Pill active={!active.category} onClick={() => commit({ category: "" })}>
          All categories
        </Pill>
        {categories.data?.map((c) => (
          <Pill key={c.id} active={active.category === c.slug} onClick={() => commit({ category: c.slug })}>
            {c.name}
          </Pill>
        ))}
      </div>

      <form onSubmit={onSubmit} className="panel editorial-enter mt-4 grid grid-cols-2 items-end gap-3 p-4 md:grid-cols-12" style={prefs.stagger(1)}>
        <Field label="Search" className="col-span-2 md:col-span-4">
          <Input value={draft.search} onChange={(e) => setDraft({ ...draft, search: e.target.value })} placeholder="Search listings…" />
        </Field>
        <Field label="Condition" className="md:col-span-2">
          <Select value={draft.condition} onChange={(e) => setDraft({ ...draft, condition: e.target.value })}>
            <option value="">Any</option>
            <option value="new">New</option>
            <option value="used">Used</option>
          </Select>
        </Field>
        <Field label="Min price" className="md:col-span-2">
          <Input type="number" min="0" value={draft.min_price} onChange={(e) => setDraft({ ...draft, min_price: e.target.value })} />
        </Field>
        <Field label="Max price" className="md:col-span-2">
          <Input type="number" min="0" value={draft.max_price} onChange={(e) => setDraft({ ...draft, max_price: e.target.value })} />
        </Field>
        <Field label="Sort by" className="col-span-2 md:col-span-2">
          <Select value={draft.ordering} onChange={(e) => setDraft({ ...draft, ordering: e.target.value })}>
            <option value="">Newest</option>
            <option value="price">Price: low to high</option>
            <option value="-price">Price: high to low</option>
            <option value="-views_count">Most viewed</option>
          </Select>
        </Field>
        <div className="col-span-2 flex justify-end gap-2 md:col-span-12">
          {hasFilters && (
            <Button type="button" variant="ghost" onClick={() => setParams({}, { viewTransition: true })}>
              Clear
            </Button>
          )}
          <Button type="submit" variant="secondary">
            Apply filters
          </Button>
        </div>
      </form>

      <p className="mt-4 h-4 text-xs text-muted-foreground">
        {listings.isSuccess && `Showing ${items.length}${listings.data.count > items.length ? ` of ${listings.data.count}` : ""} listing${listings.data.count === 1 ? "" : "s"}`}
      </p>

      <div className={cn("mt-3 grid gap-5 transition-opacity sm:grid-cols-2 lg:grid-cols-3", listings.isPlaceholderData && "opacity-60")}>
        {listings.isPending && Array.from({ length: 6 }, (_, i) => <ListingSkeleton key={i} view="grid" />)}
        {listings.isError && (
          <div className="col-span-full">
            <ErrorState message={(listings.error as Error).message} onRetry={() => listings.refetch()} />
          </div>
        )}
        {listings.isSuccess && items.length === 0 && (
          <div className="panel col-span-full">
            <EmptyState icon={<SearchX size={20} />} title="No listings match those filters" hint="Try widening the price range or clearing the search." />
          </div>
        )}
        {items.map((item, index) => (
          <ListingCard key={item.id} item={item} view="grid" density={prefs.density} style={prefs.stagger(Math.min(index, 8))} />
        ))}
      </div>
    </div>
  );
}
