import { useMutation } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";
import { useState } from "react";
import { getListingCategoryChildren, type CategoryBranchNode } from "../api/listing";

export function ListingCategoryBrowse({ draftId, starts, onSelect }: { draftId: string; starts: CategoryBranchNode[]; onSelect: (node: CategoryBranchNode) => void }) {
  const [trail, setTrail] = useState<CategoryBranchNode[]>([]);
  const [categoryId, setCategoryId] = useState("");
  const browse = useMutation({ mutationFn: ({ node }: { node: CategoryBranchNode; next: CategoryBranchNode[] }) => getListingCategoryChildren(draftId, node.category_id),
    onSuccess: (branch, variables) => setTrail([...variables.next, branch.category]) });
  const open = (node: CategoryBranchNode, next = trail) => browse.mutate({ node, next });
  return <section aria-label="Browse eBay categories" className="space-y-3 border-t pt-3">
    <nav aria-label="Category breadcrumb" className="flex flex-wrap gap-1">
      <button className="btn-secondary" type="button" onClick={() => { setTrail([]); browse.reset(); }}>eBay AU</button>
      {trail.map((node, index) => <button className="btn-secondary" type="button" key={node.category_id} onClick={() => open(node, trail.slice(0, index))}>{node.category_name}</button>)}
    </nav>
    {!trail.length ? <><p className="listing-source">Open a known branch or a search ancestor. Only leaf categories can be selected.</p>
      {starts.map((node) => <button key={node.category_id} className="btn-secondary listing-category-option" type="button" onClick={() => open(node, [])}>Browse {node.category_name}<ChevronRight size={18} /></button>)}
      <label className="label"><span>Browse from category ID</span><input className="field" value={categoryId} inputMode="numeric" onChange={(event) => setCategoryId(event.target.value)} /></label>
      <button className="btn-secondary" type="button" disabled={!/^\d+$/.test(categoryId) || browse.isPending} onClick={() => open({ category_id: categoryId, category_name: categoryId }, [])}>Open branch</button>
    </> : null}
    {browse.isPending ? <p role="status">Loading selected category level...</p> : null}
    {browse.error ? <p role="alert">Category browse failed. Your mapping is unchanged; retry or use search.</p> : null}
    {trail.length && !browse.isPending && browse.data ? <><p className="listing-source">{browse.data.provenance} · Fetched: {new Date(browse.data.fetched_at).toLocaleString()}</p>
      {browse.data.category.is_leaf === true ? <button className="btn-primary" type="button" onClick={() => onSelect(browse.data.category)}>Select {browse.data.category.category_name}</button> : null}
      {browse.data.children.map((node) => <button className="btn-secondary listing-category-option" type="button" key={node.category_id} onClick={() => node.is_leaf === true ? onSelect(node) : open(node)}>{node.is_leaf === true ? "Select" : "Open"} {node.category_name}{node.is_leaf !== true ? <ChevronRight size={18} /> : null}</button>)}
    </> : null}
  </section>;
}
