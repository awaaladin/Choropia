import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/Button";
import { Input, Select } from "@/components/ui";
import { errorMessage } from "@/lib/actions";
import { api } from "@/lib/api";
import type { Area } from "@/lib/types";

const ADD = "__add__";

/** Pick an area of Uyo. The list starts with common areas; anyone can add one that is missing. */
export function AreaSelect({ value, onChange, placeholder = "Choose an area" }: { value: number | null; onChange: (area: Area) => void; placeholder?: string }) {
  const queryClient = useQueryClient();
  const areas = useQuery({ queryKey: ["areas"], queryFn: api.dispatch.areas, staleTime: 5 * 60_000 });
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);

  const add = async () => {
    setSaving(true);
    try {
      const area = await api.dispatch.addArea(name);
      await queryClient.invalidateQueries({ queryKey: ["areas"] });
      onChange(area);
      setAdding(false);
      setName("");
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-2">
      <Select
        value={value ?? ""}
        onChange={(e) => {
          if (e.target.value === ADD) return setAdding(true);
          const area = areas.data?.find((a) => a.id === Number(e.target.value));
          if (area) onChange(area);
        }}
      >
        <option value="">{placeholder}</option>
        {areas.data?.map((a) => (
          <option key={a.id} value={a.id}>
            {a.name}
          </option>
        ))}
        <option value={ADD}>+ Add an area that is missing</option>
      </Select>
      {adding && (
        <div className="flex gap-2">
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Area name, for example Ikot Ishie" maxLength={80} autoFocus />
          <Button type="button" onClick={add} loading={saving} disabled={name.trim().length < 3}>
            Add
          </Button>
          <Button type="button" variant="secondary" onClick={() => setAdding(false)}>
            Cancel
          </Button>
        </div>
      )}
    </div>
  );
}
