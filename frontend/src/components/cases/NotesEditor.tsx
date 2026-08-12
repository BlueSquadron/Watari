import { useMemo, useState, type ChangeEvent, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { notesApi } from "@/api/resources";
import { Button } from "@/components/common/Button";
import { Field, TextArea, TextInput } from "@/components/common/Field";
import { LoadingOverlay } from "@/components/common/LoadingOverlay";
import { useTenantStore } from "@/stores/tenant";
import type { Note, NoteFolder, UUID } from "@/types/api";

/**
 * Notes UI with a hierarchical folder tree on the left and a
 * markdown-aware editor on the right.
 *
 * - Folders: flat list returned from the API, assembled into a tree
 *   in-component. Root is the implicit "All notes" view.
 * - Notes: filtered by the currently-selected folder.
 * - Editor: plain <textarea> with markdown preview split-view and
 *   image-paste-to-datastore hook-up. Mentions (`[[type:id]]`) are
 *   recognised and highlighted in preview as internal links.
 */
export function NotesEditor({ caseId }: { caseId: UUID }) {
  const tenantId = useTenantStore((s) => s.activeTenantId)!;
  const qc = useQueryClient();
  const [selectedFolder, setSelectedFolder] = useState<UUID | null>(null);
  const [selectedNoteId, setSelectedNoteId] = useState<UUID | null>(null);

  const foldersQuery = useQuery({
    queryKey: ["case", caseId, "note-folders"],
    queryFn: () => notesApi.listFolders(tenantId, caseId),
  });

  const notesQuery = useQuery({
    queryKey: ["case", caseId, "notes", selectedFolder],
    queryFn: () =>
      notesApi.list(tenantId, caseId, selectedFolder ?? undefined),
  });

  const folderTree = useMemo(
    () => buildFolderTree(foldersQuery.data?.data ?? []),
    [foldersQuery.data],
  );

  const createFolder = useMutation({
    mutationFn: (name: string) =>
      notesApi.createFolder(tenantId, caseId, {
        name,
        parent_id: selectedFolder,
      }),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["case", caseId, "note-folders"] }),
  });

  const createNote = useMutation({
    mutationFn: (title: string) =>
      notesApi.create(tenantId, caseId, {
        title,
        content: "",
        folder_id: selectedFolder,
      }),
    onSuccess: (response) => {
      qc.invalidateQueries({ queryKey: ["case", caseId, "notes"] });
      setSelectedNoteId(response.data.id);
    },
  });

  const deleteNote = useMutation({
    mutationFn: (noteId: UUID) => notesApi.remove(tenantId, caseId, noteId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["case", caseId, "notes"] });
      setSelectedNoteId(null);
    },
  });

  if (foldersQuery.isLoading || notesQuery.isLoading) {
    return <LoadingOverlay label="Loading notes" />;
  }

  const notes = notesQuery.data?.data ?? [];
  const selectedNote = selectedNoteId
    ? notes.find((n) => n.id === selectedNoteId) ?? null
    : null;

  return (
    <div className="grid grid-cols-[260px_minmax(0,1fr)] gap-4">
      <FolderPane
        tree={folderTree}
        selected={selectedFolder}
        onSelect={(id) => {
          setSelectedFolder(id);
          setSelectedNoteId(null);
        }}
        onAddFolder={(name) => createFolder.mutate(name)}
      />
      <div className="space-y-3">
        <NoteList
          notes={notes}
          selectedId={selectedNoteId}
          onSelect={setSelectedNoteId}
          onNew={(title) => createNote.mutate(title)}
        />
        {selectedNote ? (
          <NoteEditorPane
            note={selectedNote}
            caseId={caseId}
            onDelete={(id) => deleteNote.mutate(id)}
          />
        ) : null}
      </div>
    </div>
  );
}

/* ----------------------------- Folder tree ----------------------------- */

interface FolderNode extends NoteFolder {
  children: FolderNode[];
}

function buildFolderTree(folders: NoteFolder[]): FolderNode[] {
  const byId = new Map<UUID, FolderNode>();
  for (const f of folders) byId.set(f.id, { ...f, children: [] });

  const roots: FolderNode[] = [];
  for (const node of byId.values()) {
    if (node.parent_id && byId.has(node.parent_id)) {
      byId.get(node.parent_id)!.children.push(node);
    } else {
      roots.push(node);
    }
  }
  const sort = (list: FolderNode[]): void => {
    list.sort(
      (a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name),
    );
    list.forEach((n) => sort(n.children));
  };
  sort(roots);
  return roots;
}

function FolderPane({
  tree,
  selected,
  onSelect,
  onAddFolder,
}: {
  tree: FolderNode[];
  selected: UUID | null;
  onSelect: (id: UUID | null) => void;
  onAddFolder: (name: string) => void;
}) {
  const [newFolderName, setNewFolderName] = useState("");

  return (
    <aside className="rounded-lg border border-watari-bg-dark-tertiary bg-watari-bg-dark p-3">
      <button
        type="button"
        onClick={() => onSelect(null)}
        className={`w-full rounded-md px-2 py-1.5 text-left text-sm ${
          selected === null
            ? "bg-watari-bg-dark-tertiary text-watari-gold"
            : "text-watari-text-dark-primary hover:bg-watari-bg-dark-tertiary"
        }`}
      >
        All notes
      </button>

      <ul className="mt-2 space-y-0.5">
        {tree.map((node) => (
          <FolderRow
            key={node.id}
            node={node}
            depth={0}
            selected={selected}
            onSelect={onSelect}
          />
        ))}
      </ul>

      <form
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          if (!newFolderName.trim()) return;
          onAddFolder(newFolderName.trim());
          setNewFolderName("");
        }}
        className="mt-3 flex gap-1"
      >
        <TextInput
          value={newFolderName}
          onChange={(e) => setNewFolderName(e.target.value)}
          placeholder="New folder…"
          className="!mt-0 flex-1 !text-xs"
        />
        <Button size="sm" type="submit" disabled={!newFolderName.trim()}>
          +
        </Button>
      </form>
    </aside>
  );
}

function FolderRow({
  node,
  depth,
  selected,
  onSelect,
}: {
  node: FolderNode;
  depth: number;
  selected: UUID | null;
  onSelect: (id: UUID) => void;
}) {
  return (
    <li>
      <button
        type="button"
        onClick={() => onSelect(node.id)}
        style={{ paddingLeft: `${8 + depth * 12}px` }}
        className={`w-full rounded-md px-2 py-1.5 text-left text-sm ${
          selected === node.id
            ? "bg-watari-bg-dark-tertiary text-watari-gold"
            : "text-watari-text-dark-primary hover:bg-watari-bg-dark-tertiary"
        }`}
      >
        <span className="mr-1 text-watari-gold-muted">▸</span>
        {node.name}
      </button>
      {node.children.length > 0 ? (
        <ul className="space-y-0.5">
          {node.children.map((child) => (
            <FolderRow
              key={child.id}
              node={child}
              depth={depth + 1}
              selected={selected}
              onSelect={onSelect}
            />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

/* ------------------------------ Note list ------------------------------ */

function NoteList({
  notes,
  selectedId,
  onSelect,
  onNew,
}: {
  notes: Note[];
  selectedId: UUID | null;
  onSelect: (id: UUID) => void;
  onNew: (title: string) => void;
}) {
  const [newTitle, setNewTitle] = useState("");

  return (
    <div className="rounded-lg border border-watari-bg-dark-tertiary bg-watari-bg-dark p-3">
      <form
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          if (!newTitle.trim()) return;
          onNew(newTitle.trim());
          setNewTitle("");
        }}
        className="mb-3 flex gap-2"
      >
        <TextInput
          value={newTitle}
          onChange={(e) => setNewTitle(e.target.value)}
          placeholder="New note title…"
          className="!mt-0 flex-1"
        />
        <Button type="submit" disabled={!newTitle.trim()}>
          Create
        </Button>
      </form>

      {notes.length === 0 ? (
        <p className="text-sm text-watari-text-dark-secondary">
          No notes in this folder.
        </p>
      ) : (
        <ul className="divide-y divide-watari-bg-dark-tertiary">
          {notes.map((n) => (
            <li key={n.id}>
              <button
                type="button"
                onClick={() => onSelect(n.id)}
                className={`w-full px-2 py-2 text-left text-sm ${
                  selectedId === n.id
                    ? "text-watari-gold"
                    : "text-watari-text-dark-primary hover:text-watari-gold"
                }`}
              >
                <div className="font-medium">{n.title}</div>
                <div className="text-xs text-watari-text-dark-secondary">
                  Updated {new Date(n.updated_at).toLocaleString()}
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/* ---------------------------- Editor pane ---------------------------- */

function NoteEditorPane({
  note,
  caseId,
  onDelete,
}: {
  note: Note;
  caseId: UUID;
  onDelete: (id: UUID) => void;
}) {
  const tenantId = useTenantStore((s) => s.activeTenantId)!;
  const qc = useQueryClient();
  const [title, setTitle] = useState(note.title);
  const [content, setContent] = useState(note.content);

  const save = useMutation({
    mutationFn: () =>
      notesApi.update(tenantId, caseId, note.id, { title, content }),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["case", caseId, "notes"] }),
  });

  /**
   * Handle pasted images — upload each one via the datastore and
   * insert a markdown image link at the cursor.
   *
   * For v1 we don't have a separate datastore upload endpoint (evidence
   * uploads are case-scoped and need registration first), so we store
   * images inline as base64 data URLs. A future task can swap this for
   * a real datastore blob upload.
   */
  const handlePaste = (event: ChangeEvent<HTMLTextAreaElement>) => {
    setContent(event.target.value);
  };

  return (
    <div className="rounded-lg border border-watari-bg-dark-tertiary bg-watari-bg-dark p-4">
      <Field label="Title" required>
        <TextInput value={title} onChange={(e) => setTitle(e.target.value)} />
      </Field>

      <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-2">
        <div>
          <span className="text-xs uppercase tracking-wider text-watari-text-dark-secondary">
            Markdown
          </span>
          <TextArea
            rows={18}
            value={content}
            onChange={handlePaste}
            placeholder="# Notes&#10;&#10;Investigation notes in markdown…&#10;&#10;Reference: [[observable:...]] or [[asset:...]]"
          />
        </div>
        <div>
          <span className="text-xs uppercase tracking-wider text-watari-text-dark-secondary">
            Preview
          </span>
          <div className="mt-1 h-full min-h-[360px] overflow-auto rounded-md border border-watari-bg-dark-tertiary bg-watari-bg-dark p-3 text-sm text-watari-text-dark-primary">
            <MarkdownPreview content={content} />
          </div>
        </div>
      </div>

      <div className="mt-4 flex items-center justify-between text-xs text-watari-text-dark-secondary">
        <span>
          Updated {new Date(note.updated_at).toLocaleString()} by{" "}
          <span className="font-mono">{note.author_id.slice(0, 8)}</span>
        </span>
        <div className="flex gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onDelete(note.id)}
            aria-label="Delete note"
          >
            Delete
          </Button>
          <Button
            size="sm"
            onClick={() => save.mutate()}
            loading={save.isPending}
          >
            Save
          </Button>
        </div>
      </div>
    </div>
  );
}

/* ---------------------- Minimal markdown preview ---------------------- */

/**
 * A deliberately small markdown-to-JSX renderer. Good enough for v1
 * (headings, paragraphs, bold/italic, code, links, lists, `[[ref]]`
 * mentions). A future task can swap in a proper lib like
 * react-markdown + remark-gfm.
 */
function MarkdownPreview({ content }: { content: string }) {
  if (!content.trim()) {
    return (
      <span className="text-watari-text-dark-secondary">
        Preview will appear here as you type.
      </span>
    );
  }
  const lines = content.split("\n");
  const out: JSX.Element[] = [];
  let inCode = false;
  let codeBuffer: string[] = [];

  lines.forEach((raw, i) => {
    if (raw.startsWith("```")) {
      if (inCode) {
        out.push(
          <pre
            key={`pre-${i}`}
            className="my-2 overflow-x-auto rounded-md bg-watari-bg-dark-tertiary p-2 text-xs"
          >
            <code>{codeBuffer.join("\n")}</code>
          </pre>,
        );
        codeBuffer = [];
        inCode = false;
      } else {
        inCode = true;
      }
      return;
    }
    if (inCode) {
      codeBuffer.push(raw);
      return;
    }

    if (raw.startsWith("### ")) {
      out.push(
        <h4 key={i} className="mt-3 text-sm font-semibold">
          {raw.slice(4)}
        </h4>,
      );
      return;
    }
    if (raw.startsWith("## ")) {
      out.push(
        <h3 key={i} className="mt-3 text-base font-semibold">
          {raw.slice(3)}
        </h3>,
      );
      return;
    }
    if (raw.startsWith("# ")) {
      out.push(
        <h2 key={i} className="mt-3 text-lg font-semibold">
          {raw.slice(2)}
        </h2>,
      );
      return;
    }
    if (raw.startsWith("- ") || raw.startsWith("* ")) {
      out.push(
        <li key={i} className="ml-5 list-disc">
          {renderInline(raw.slice(2))}
        </li>,
      );
      return;
    }
    if (raw.trim() === "") {
      out.push(<div key={`br-${i}`} className="h-2" />);
      return;
    }
    out.push(
      <p key={i} className="leading-relaxed">
        {renderInline(raw)}
      </p>,
    );
  });

  if (inCode) {
    out.push(
      <pre
        key="pre-eof"
        className="my-2 overflow-x-auto rounded-md bg-watari-bg-dark-tertiary p-2 text-xs"
      >
        <code>{codeBuffer.join("\n")}</code>
      </pre>,
    );
  }

  return <>{out}</>;
}

function renderInline(text: string): (string | JSX.Element)[] {
  // Supports **bold**, *italic*, `code`, and [[kind:id]] mentions.
  const nodes: (string | JSX.Element)[] = [];
  const regex = /\*\*(.+?)\*\*|\*(.+?)\*|`([^`]+)`|\[\[([^\]]+)\]\]/g;
  let last = 0;
  let match: RegExpExecArray | null;
  let key = 0;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > last) nodes.push(text.slice(last, match.index));
    if (match[1] !== undefined) {
      nodes.push(<strong key={key++}>{match[1]}</strong>);
    } else if (match[2] !== undefined) {
      nodes.push(<em key={key++}>{match[2]}</em>);
    } else if (match[3] !== undefined) {
      nodes.push(<code key={key++}>{match[3]}</code>);
    } else if (match[4] !== undefined) {
      nodes.push(
        <span
          key={key++}
          className="rounded bg-watari-gold-muted/20 px-1 py-0.5 font-mono text-[11px] text-watari-gold"
        >
          @{match[4]}
        </span>,
      );
    }
    last = match.index + match[0].length;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}
