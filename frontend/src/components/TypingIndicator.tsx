export default function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 px-4 py-3">
      <div className="flex gap-1">
        <span className="w-2 h-2 rounded-full bg-primary-foreground/70 animate-bounce" style={{ animationDelay: "0ms" }} />
        <span className="w-2 h-2 rounded-full bg-primary-foreground/70 animate-bounce" style={{ animationDelay: "150ms" }} />
        <span className="w-2 h-2 rounded-full bg-primary-foreground/70 animate-bounce" style={{ animationDelay: "300ms" }} />
      </div>
      <span className="text-sm text-primary-foreground/70 ml-2">Typing...</span>
    </div>
  );
}
