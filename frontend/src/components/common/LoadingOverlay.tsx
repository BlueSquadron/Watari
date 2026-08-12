export function LoadingOverlay({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-watari-gold border-r-transparent" />
      <p className="text-sm text-watari-text-dark-secondary">{label}</p>
    </div>
  );
}
