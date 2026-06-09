import { useMutation, useQuery } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { listCategories } from "../../api/categories";
import { createItem, uploadItemPhoto } from "../../api/items";
import { listLocations } from "../../api/locations";
import { CategorySelect } from "../../components/CategorySelect";
import { EmptyState } from "../../components/EmptyState";
import { LocationSelect } from "../../components/LocationSelect";
import { PhotoUploader } from "../../components/PhotoUploader";
import type { ItemFormPayload, UUID } from "../../types";

const conditionOptions = [
  ["ungraded", "Ungraded"],
  ["new", "New"],
  ["like_new", "Like new"],
  ["very_good", "Very good"],
  ["good", "Good"],
  ["acceptable", "Acceptable"],
  ["for_parts", "For parts"]
];

export function AddItem() {
  const navigate = useNavigate();
  const categories = useQuery({ queryKey: ["categories"], queryFn: listCategories });
  const locations = useQuery({ queryKey: ["locations"], queryFn: listLocations });
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState<UUID | null>(null);
  const [condition, setCondition] = useState("ungraded");
  const [location, setLocation] = useState<UUID | null>(null);
  const [acquisitionCost, setAcquisitionCost] = useState("");
  const [estimatedValue, setEstimatedValue] = useState("");
  const [notes, setNotes] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [formError, setFormError] = useState("");

  const submit = useMutation({
    mutationFn: async () => {
      const payload: ItemFormPayload = {
        title: title.trim(),
        category,
        condition,
        location,
        acquisition_cost: acquisitionCost || null,
        estimated_value: estimatedValue || null,
        notes,
        attributes: {}
      };
      const item = await createItem(payload);
      for (const file of files) {
        await uploadItemPhoto(item.id, file, "other");
      }
      return item;
    },
    onSuccess: (item) => navigate(`/inventory/${item.id}`)
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!title.trim()) {
      setFormError("Title is required.");
      return;
    }
    if (files.length === 0) {
      setFormError("Add at least one photo.");
      return;
    }
    setFormError("");
    submit.mutate();
  }

  return (
    <div className="mx-auto w-full max-w-3xl p-4 sm:p-6 lg:p-8">
      <h1 className="page-title">Add Item</h1>
      <form className="mt-5 space-y-5" onSubmit={handleSubmit}>
        <PhotoUploader files={files} onFiles={setFiles} />

        {formError ? <EmptyState title={formError} /> : null}
        {submit.error ? <EmptyState title="Unable to save item" detail="Check your Django admin session and try again." /> : null}

        <div className="grid gap-4 sm:grid-cols-2">
          <label className="label sm:col-span-2">
            <span>Title</span>
            <input className="field" value={title} onChange={(event) => setTitle(event.target.value)} />
          </label>
          <label className="label">
            <span>Category</span>
            <CategorySelect categories={categories.data?.results ?? []} value={category} onChange={setCategory} />
          </label>
          <label className="label">
            <span>Condition</span>
            <select className="field" value={condition} onChange={(event) => setCondition(event.target.value)}>
              {conditionOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          <label className="label">
            <span>Location</span>
            <LocationSelect locations={locations.data?.results ?? []} value={location} onChange={setLocation} />
          </label>
          <label className="label">
            <span>Acquisition cost</span>
            <input className="field" inputMode="decimal" value={acquisitionCost} onChange={(event) => setAcquisitionCost(event.target.value)} />
          </label>
          <label className="label">
            <span>Estimated value</span>
            <input className="field" inputMode="decimal" value={estimatedValue} onChange={(event) => setEstimatedValue(event.target.value)} />
          </label>
          <label className="label sm:col-span-2">
            <span>Notes</span>
            <textarea className="field min-h-28" value={notes} onChange={(event) => setNotes(event.target.value)} />
          </label>
        </div>

        <button className="btn-primary w-full sm:w-auto" disabled={submit.isPending} type="submit">
          {submit.isPending ? "Saving" : "Save item"}
        </button>
      </form>
    </div>
  );
}
