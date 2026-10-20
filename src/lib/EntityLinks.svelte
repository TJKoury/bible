<script>
  import { onMount } from 'svelte';
  import { json } from './data.js';
  import { linkedArticles, passagePlaces, articleList } from './geography.js';
  import Icon from './Icon.svelte';
  let { book, chapter, verse, text = '', gloss = '', aligned = true, onArticle, onMap } = $props();
  let geography = $state(null);
  let encyclopedia = $state(null);
  const places = $derived(aligned ? passagePlaces(geography, book, chapter, verse, 'verse') : []);
  const articles = $derived.by(() => {
    const result = linkedArticles(encyclopedia, `${text} ${gloss}`);
    for (const place of places) {
      if (place.articleId && !result.some(a => a.id === place.articleId)) result.unshift({ id: place.articleId, title: place.name });
    }
    return result.slice(0, 8);
  });
  const nameMatches = $derived.by(() => {
    const name = gloss.toLowerCase().replace(/\[[^\]]*\]/g,'').replace(/^(of |the |to |from )+/g,'').replace(/[^\p{L}\p{N}\s]/gu,'').trim();
    if (name.length < 3 || name.split(' ').length > 3) return [];
    return articleList(encyclopedia).filter(a => a.category === 'person' &&
      [a.title,...(a.aliases || [])].some(alias => ` ${alias.toLowerCase().replace(/[^\p{L}\p{N}]+/gu,' ')} `.includes(` ${name} `))
    ).slice(0,4);
  });
  onMount(async () => {
    const results = await Promise.allSettled([json('/data/geography/index.json'), json('/data/encyclopedia/index.json')]);
    if (results[0].status === 'fulfilled') geography = results[0].value;
    if (results[1].status === 'fulfilled') encyclopedia = results[1].value;
  });
</script>
{#if articles.length || places.length || nameMatches.length}
  <div class="entity-links">
    <div class="section-label">PEOPLE, PLACES & CONTEXT</div>
    {#each articles as article}<button onclick={() => onArticle(article.id)}><Icon name="compass" /><span>Explore {article.title}</span><Icon name="arrow-up-right" /></button>{/each}
    {#if nameMatches.length}<p class="source-caption">Name matches for the selected word · choose the person in context.</p>{#each nameMatches as article}<button onclick={() => onArticle(article.id)}><Icon name="compass" /><span>{article.title}</span><Icon name="arrow-up-right" /></button>{/each}{/if}
    {#if places.length}<button onclick={onMap}><Icon name="map" /><span>Map this passage</span><Icon name="arrow-right" /></button>{/if}
  </div>
{/if}
