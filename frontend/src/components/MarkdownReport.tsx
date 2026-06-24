export function MarkdownReport({ markdown }: { markdown: string }) {
  const blocks = markdown.split(/\n{2,}/);

  return (
    <div className="markdown-report">
      {blocks.map((block, index) => {
        const lines = block.split("\n");
        const firstLine = lines[0] ?? "";

        if (firstLine.startsWith("# ")) {
          return <h2 key={index}>{firstLine.slice(2)}</h2>;
        }

        if (firstLine.startsWith("## ")) {
          return <h3 key={index}>{firstLine.slice(3)}</h3>;
        }

        if (lines.every((line) => line.startsWith("- "))) {
          return (
            <ul key={index}>
              {lines.map((line) => (
                <li key={line}>{renderInline(line.slice(2))}</li>
              ))}
            </ul>
          );
        }

        return <p key={index}>{renderInline(block)}</p>;
      })}
    </div>
  );
}

function renderInline(text: string) {
  const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g);

  return parts.map((part, index) => {
    if (part.startsWith("`") && part.endsWith("`")) {
      return <code key={index}>{part.slice(1, -1)}</code>;
    }

    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }

    return part;
  });
}
