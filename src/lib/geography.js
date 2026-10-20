export function passagePlaces(data, book, chapter, verse, scope = 'chapter') {
  if (!data) return [];
  const ids = scope === 'verse'
    ? data.verses?.[`${book}.${chapter}.${verse}`]
    : data.chapters?.[`${book}.${chapter}`];
  return [...new Set(ids || [])].map(id => data.places[id]).filter(Boolean);
}

export function mapPoints(places) {
  return places.flatMap(place => (place.candidates || []).filter(c =>
    Number.isFinite(c.lon) && Number.isFinite(c.lat) &&
    Math.abs(c.lon) <= 180 && Math.abs(c.lat) <= 90
  ).map((candidate, index) => ({
    ...candidate, key: `${place.id}-${candidate.id || index}`,
    placeId: place.id, placeName: place.name,
    disputed: place.candidates.length > 1,
    label: `${place.name} · ${candidate.name || 'candidate site'}`,
  })));
}

export function articleList(index) {
  return Array.isArray(index?.articles) ? index.articles : Object.values(index?.articles || {});
}

export function linkedArticles(index, text) {
  const normalized = ` ${text.toLocaleLowerCase().replace(/[^\p{L}\p{N}]+/gu, ' ')} `;
  return articleList(index).filter(article => {
    if (article.autoLink === false) return false;
    const aliases = article.aliases?.length ? article.aliases : [article.title];
    return aliases.some(alias => {
      const name = alias.toLocaleLowerCase().replace(/[^\p{L}\p{N}]+/gu, ' ').trim();
      return name.length >= 3 && normalized.includes(` ${name} `);
    });
  });
}
