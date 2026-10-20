const cache = new Map();

export function json(path) {
  if (!cache.has(path)) {
    cache.set(
      path,
      fetch(path)
        .then((response) => {
          if (!response.ok)
            throw new Error(`Could not load ${path} (${response.status}).`);
          return response.json();
        })
        .catch((error) => {
          cache.delete(path);
          throw error;
        }),
    );
  }
  return cache.get(path);
}

export function shortName(id) {
  return (
    {
      KJVPCE: "KJV",
      Geneva1599: "GNV",
      Rotherham: "EBR",
      Webster: "WBT",
      Darby: "DBY",
    }[id] || id
  );
}

export function referenceLabel(ref, books) {
  const [b, c, v] = String(ref).split(".").map(Number);
  return `${books.find((book) => book.id === b)?.name || "Book " + b} ${c}:${v}`;
}

export function parseReference(query, books) {
  const input = query.trim().replace(/^psalm\b/i, "Psalms");
  const match = input.match(/^(.+?)\s+(\d+)(?::(\d+))?$/);
  if (!match) return null;
  const name = match[1].toLowerCase().replace(/\s/g, "");
  const book = books.find(
    (book) => book.name.toLowerCase().replace(/\s/g, "") === name,
  );
  if (!book) return null;
  return {
    book: book.id,
    chapter: Number(match[2]),
    verse: Number(match[3] || 1),
  };
}

export function inverseMapping(mapping) {
  const inverse = {};
  for (const [english, originals] of Object.entries(mapping)) {
    for (const original of originals) (inverse[original] ??= []).push(english);
  }
  return inverse;
}

export function nativeToEnglish(ref, inverse) {
  return inverse[ref] || [ref];
}

export async function lookupLemma(lemma, language) {
  const digest = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(lemma),
  );
  const shard = new Uint8Array(digest)[0].toString(16).padStart(2, "0");
  const data = await json(`/data/lemmas/${language}/${shard}.json`);
  return data[lemma] || null;
}

export async function versePreview(ref, edition = "BSB") {
  const [b, c, v] = ref.split(".");
  const book = await json(`/data/translations/${edition}/${b}.json`);
  return (
    book[c]?.[v] || "No verse text at this reference in the downloaded source."
  );
}

export function storageRead(key, fallback) {
  try {
    return JSON.parse(localStorage.getItem(key)) ?? fallback;
  } catch {
    return fallback;
  }
}

export function storageWrite(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}
