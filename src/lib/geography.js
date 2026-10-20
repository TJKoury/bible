export function passagePlaces(data, book, chapter, verse, scope = 'chapter') {
  if (!data) return [];
  const ids = scope === 'verse'
    ? data.verses?.[`${book}.${chapter}.${verse}`]
    : data.chapters?.[`${book}.${chapter}`];
  return [...new Set(ids || [])].map(id => data.places[id]).filter(Boolean);
}

export function candidateKey(placeId, candidate, index) {
  // Source candidate IDs can repeat within a place. Use the original array
  // position so list selection and mapped candidates share one unique identity.
  return `${placeId}-${candidate.id || 'candidate'}-${index}`;
}

export function mapPoints(places) {
  return places.flatMap(place => (place.candidates || []).flatMap((candidate, index) => {
    if (!Number.isFinite(candidate.lon) || !Number.isFinite(candidate.lat) ||
      Math.abs(candidate.lon) > 180 || Math.abs(candidate.lat) > 90) return [];
    return [{
      ...candidate, key: candidateKey(place.id, candidate, index),
      placeId: place.id, placeName: place.name,
      disputed: place.candidates.length > 1,
      label: `${place.name} · ${candidate.name || 'candidate site'}`,
    }];
  }));
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
